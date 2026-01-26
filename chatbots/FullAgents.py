# chatbots/FullAgents.py
from __future__ import annotations

import os
import json
import time
import random
from typing import Tuple, Dict, Any, Optional

from typing_extensions import TypedDict

from langchain_together import Together
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ----------------------------
# CONFIG / CONSTANTS
# ----------------------------
DEBUGGING_MODE = True
NULL_STRING = " "

FULL_TEXT_MAX_TOKENS = 3584
FULL_TEXT_MIN_TOKENS = 1792

# Approx conversion: 1 token ~ 5 chars (consistent with SingularAgents)
_CHARS_PER_TOKEN = 5

def _tok_to_char(n_tokens: int) -> int:
    return max(0, int(n_tokens) * _CHARS_PER_TOKEN)

FULL_MIN_CHARS = _tok_to_char(FULL_TEXT_MIN_TOKENS)
FULL_MAX_CHARS = _tok_to_char(FULL_TEXT_MAX_TOKENS)

# Constraint: DeepSeek-V3 ONLY
COMPILER_MODEL = "deepseek-ai/DeepSeek-V3"

SYSTEM_DIRECTIVE_COMPILER = """You are the final compiler agent in a multi-agent writing pipeline.

HIGHEST PRIORITY RULES:
- Output MUST be plain Markdown ONLY (NOT JSON).
- Do NOT include code blocks (```), HTML tags, or templating syntax.
- Do not invent facts beyond what the user prompt and drafts contain.
- Preserve placeholders exactly as-is when they appear (e.g., COMPANY_NAME, CALL_NUMBER, LINK).
- Remove repetition, normalise tone, and ensure the final piece reads as one coherent blog/page.
- Do not reference internal pipeline mechanics or agent names (e.g., “Introduction Agent”).
- Produce a clean structure with headings and subheadings where appropriate.

LENGTH TARGET:
- Aim for a complete output that is within the target length window.
"""

_LABELS_IN_ORDER = [
    "Introduction Agent:",
    "Final CTA Agent:",
    "FAQs Agent:",
    "Business Description Agent:",
    "Short CTA Agent:",
    "Integrate References Agent:",
]

# ----------------------------
# LLM factory (Together)
# ----------------------------
def _make_llm(temperature: float, max_tokens: int) -> Together:
    api_key = os.getenv("TOGETHER_API_KEY")
    if not api_key:
        raise RuntimeError("TOGETHER_API_KEY is not set in environment.")

    return Together(
        model=COMPILER_MODEL,
        temperature=temperature,
        together_api_key=str(api_key),
        max_tokens=max_tokens,
    )

# ----------------------------
# Retry/backoff for Together transient failures
# ----------------------------
def _is_transient_provider_error(msg: str) -> bool:
    m = (msg or "").lower()
    return (
        "error 500" in m
        or "http 500" in m
        or "service unavailable" in m
        or "timeout" in m
        or "temporarily" in m
        or "rate limit" in m
        or "overloaded" in m
    )

def _invoke_with_retries(llm: Together, messages, *, attempts: int = 4) -> str:
    last_err: Optional[Exception] = None
    for i in range(attempts):
        try:
            out = llm.invoke(messages)
            return out.content if hasattr(out, "content") else str(out)
        except Exception as e:
            last_err = e
            msg = str(e)
            if (not _is_transient_provider_error(msg)) or (i == attempts - 1):
                raise
            sleep_s = (0.5 * (2 ** i)) + random.uniform(0.0, 0.35)
            time.sleep(sleep_s)
    raise last_err  # pragma: no cover

# ----------------------------
# Draft extraction / cleaning
# ----------------------------
def _try_extract_content_md(maybe_json: str) -> Optional[str]:
    s = (maybe_json or "").strip()
    try:
        obj = json.loads(s)
        if isinstance(obj, dict) and isinstance(obj.get("content_md"), str):
            return obj["content_md"]
    except Exception:
        return None
    return None

def _iter_json_objects_by_brace_balance(text: str):
    if not text:
        return
    in_str = False
    escape = False
    depth = 0
    start = None

    for i, ch in enumerate(text):
        if in_str:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue

        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    end = i + 1
                    yield start, end, text[start:end]
                    start = None

def _replace_any_json_objects(text: str) -> str:
    if not text:
        return ""
    replacements = []
    for start, end, chunk in _iter_json_objects_by_brace_balance(text):
        content = _try_extract_content_md(chunk)
        if content is not None:
            replacements.append((start, end, content))
    if not replacements:
        return text

    out = text
    for start, end, content in reversed(replacements):
        out = out[:start] + content + out[end:]
    return out

def _extract_sections_by_labels(full_prompt: str) -> str:
    if not full_prompt:
        return ""

    text = full_prompt

    indices = []
    for label in _LABELS_IN_ORDER:
        idx = text.find(label)
        if idx != -1:
            indices.append((idx, label))

    if not indices:
        return _replace_any_json_objects(text)

    indices.sort(key=lambda x: x[0])
    cleaned = text

    # Replace blocks from the end to preserve indices
    for i in range(len(indices) - 1, -1, -1):
        start_idx, label = indices[i]
        content_start = start_idx + len(label)
        end_idx = indices[i + 1][0] if i + 1 < len(indices) else len(text)

        block = text[content_start:end_idx].strip()
        extracted = _try_extract_content_md(block)
        if extracted is None:
            continue

        cleaned = cleaned[:content_start] + "\n" + extracted.strip() + "\n" + cleaned[end_idx:]

    cleaned = _replace_any_json_objects(cleaned)
    return cleaned

# ----------------------------
# Generation + validation/repair
# ----------------------------
def _generate_markdown(llm: Together, prompt: str) -> str:
    messages = [
        SystemMessage(content=SYSTEM_DIRECTIVE_COMPILER),
        HumanMessage(content=prompt),
    ]
    return _invoke_with_retries(llm, messages, attempts=4)

def _validate_or_repair(llm: Together, raw_md: str, cleaned_prompt: str) -> str:
    md = (raw_md or "").strip()

    # Hard constraint: no code fences
    if "```" in md:
        repair_system = SYSTEM_DIRECTIVE_COMPILER + f"""
REPAIR MODE:
You produced output that violates constraints (e.g., code blocks).
Rewrite it as plain Markdown without code fences or HTML.
Keep meaning and structure. Return Markdown only.
"""
        md = _generate_markdown(llm, f"{repair_system}\n\nORIGINAL_OUTPUT:\n{raw_md}\n\nSOURCE_PROMPT:\n{cleaned_prompt}")

    ln = len(md)

    if ln > FULL_MAX_CHARS:
        compress_system = SYSTEM_DIRECTIVE_COMPILER + f"""
COMPRESSION MODE:
Your output is too long ({ln} chars). Rewrite to fit within {FULL_MAX_CHARS} chars.
Keep key information, remove redundancy, tighten phrasing. Return Markdown only.
"""
        md2 = _generate_markdown(llm, f"{compress_system}\n\nORIGINAL_OUTPUT:\n{md}\n\nSOURCE_PROMPT:\n{cleaned_prompt}").strip()
        if md2:
            md = md2
        if len(md) > FULL_MAX_CHARS:
            md = md[:FULL_MAX_CHARS].rstrip()

    elif ln < FULL_MIN_CHARS:
        expand_system = SYSTEM_DIRECTIVE_COMPILER + f"""
EXPANSION MODE:
Your output is too short ({ln} chars). Expand to at least {FULL_MIN_CHARS} chars.
Add structure and clarifying detail, but do NOT invent new facts. Return Markdown only.
"""
        md2 = _generate_markdown(llm, f"{expand_system}\n\nORIGINAL_OUTPUT:\n{md}\n\nSOURCE_PROMPT:\n{cleaned_prompt}").strip()
        if md2:
            md = md2
        # If still short, accept; do not loop.

    return md.strip()

# ----------------------------
# LangGraph micro-graph: prepare -> generate -> validate -> END
# ----------------------------
class _State(TypedDict, total=False):
    llm: Any
    prompt: str
    cleaned_prompt: str
    raw_md: str
    final_md: str

def _build_graph():
    g = StateGraph(_State)

    def node_prepare(state: _State) -> _State:
        state["cleaned_prompt"] = _extract_sections_by_labels(state["prompt"])
        return state

    def node_generate(state: _State) -> _State:
        llm = state["llm"]
        state["raw_md"] = _generate_markdown(llm, state["cleaned_prompt"])
        return state

    def node_validate(state: _State) -> _State:
        llm = state["llm"]
        state["final_md"] = _validate_or_repair(llm, state["raw_md"], state["cleaned_prompt"])
        return state

    g.add_node("prepare", node_prepare)
    g.add_node("generate", node_generate)
    g.add_node("validate", node_validate)

    g.set_entry_point("prepare")
    g.add_edge("prepare", "generate")
    g.add_edge("generate", "validate")
    g.add_edge("validate", END)

    return g.compile()

_GRAPH = _build_graph()

# ----------------------------
# Public API (signature preserved)
# ----------------------------
def Full_Blog_Writer(prompt: str, temperature: float) -> Tuple[str, str]:
    llm = _make_llm(temperature=temperature, max_tokens=FULL_TEXT_MAX_TOKENS)
    state: _State = {"llm": llm, "prompt": prompt}
    out = _GRAPH.invoke(state)
    return prompt, out["final_md"]

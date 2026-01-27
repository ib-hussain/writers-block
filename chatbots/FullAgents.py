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

DEBUGGING_MODE = True
NULL_STRING = " "

FULL_TEXT_MAX_TOKENS = 3584
FULL_TEXT_MIN_TOKENS = 1792

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
- Do NOT output raw variable assignment lines (e.g., "COMPANY_EMPLOYEE = ...") in the final answer.
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

# Canonical business vars you actually want (keep last occurrence only)
_CANON_VARS = [
    "COMPANY_NAME",
    "CALL_NUMBER",
    "ADDRESS",
    "STATE_NAME",
    "LINK",
    "COMPANY_EMPLOYEE",
    "USER_MESSAGE",
]

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

def _is_transient_provider_error(msg: str) -> bool:
    m = (msg or "").lower()
    return (
        "error 500" in m
        or "http 500" in m
        or "service unavailable" in m
        or "timeout" in m
        or "temporarily" in m
        or "overloaded" in m
        or "rate limit" in m
        or "connection already closed" in m
        or "connection reset" in m
    )

def _invoke_with_retries(llm: Together, messages, *, attempts: int = 4) -> str:
    last_err: Optional[Exception] = None
    for i in range(attempts):
        try:
            out = llm.invoke(messages)
            return out.content if hasattr(out, "content") else str(out)
        except Exception as e:
            last_err = e
            if (not _is_transient_provider_error(str(e))) or (i == attempts - 1):
                raise
            sleep_s = (0.5 * (2 ** i)) + random.uniform(0.0, 0.35)
            time.sleep(sleep_s)
    raise last_err  # pragma: no cover

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

def _strip_assignment_lines_keep_canon(prompt: str) -> str:
    """
    Removes spammy/injected lines like 'COMPANY_EMPLOYEE = John' repeated many times.
    Keeps only the last occurrence of each canonical var listed in _CANON_VARS.
    """
    if not prompt:
        return ""

    lines = prompt.splitlines()
    canon_last: Dict[str, str] = {}

    # First pass: record last value for canonical vars
    for line in lines:
        s = line.strip()
        for k in _CANON_VARS:
            prefix = f"{k} ="
            if s.startswith(prefix):
                canon_last[k] = s

    # Second pass: remove ALL assignment-looking lines "WORD = ..."
    # but keep canonical vars only once (appended at end).
    kept: list[str] = []
    for line in lines:
        s = line.strip()
        if " = " in s and s.split("=", 1)[0].strip().isidentifier():
            # Drop all assignment-like lines from the main body
            continue
        kept.append(line)

    # Append canonical vars at end (stable order) using last seen values
    kept.append("")
    for k in _CANON_VARS:
        if k in canon_last:
            kept.append(canon_last[k])

    return "\n".join(kept).strip()

def _generate_markdown(llm: Together, prompt: str) -> str:
    messages = [SystemMessage(content=SYSTEM_DIRECTIVE_COMPILER), HumanMessage(content=prompt)]
    return _invoke_with_retries(llm, messages, attempts=4)

def _validate_or_repair(llm: Together, raw_md: str, cleaned_prompt: str) -> str:
    md = (raw_md or "").strip()

    # No code fences
    if "```" in md:
        repair_system = SYSTEM_DIRECTIVE_COMPILER + """
REPAIR MODE:
Rewrite the output as plain Markdown without code fences or HTML.
Return Markdown only.
"""
        md = _generate_markdown(llm, f"{repair_system}\n\nORIGINAL_OUTPUT:\n{raw_md}\n\nSOURCE_PROMPT:\n{cleaned_prompt}")

    # Length control
    ln = len(md)

    if ln > FULL_MAX_CHARS:
        compress_system = SYSTEM_DIRECTIVE_COMPILER + f"""
COMPRESSION MODE:
Rewrite to fit within {FULL_MAX_CHARS} characters. Keep key information.
Return Markdown only.
"""
        md2 = _generate_markdown(llm, f"{compress_system}\n\nORIGINAL_OUTPUT:\n{md}\n\nSOURCE_PROMPT:\n{cleaned_prompt}").strip()
        if md2:
            md = md2
        if len(md) > FULL_MAX_CHARS:
            md = md[:FULL_MAX_CHARS].rstrip()

    elif ln < FULL_MIN_CHARS:
        expand_system = SYSTEM_DIRECTIVE_COMPILER + f"""
EXPANSION MODE:
Expand to at least {FULL_MIN_CHARS} characters WITHOUT inventing new facts.
Return Markdown only.
"""
        md2 = _generate_markdown(llm, f"{expand_system}\n\nORIGINAL_OUTPUT:\n{md}\n\nSOURCE_PROMPT:\n{cleaned_prompt}").strip()
        if md2:
            md = md2

    # Final: ensure we didn't accidentally output assignment spam
    filtered_lines = []
    for line in md.splitlines():
        s = line.strip()
        if " = " in s and s.split("=", 1)[0].strip().isidentifier():
            continue
        filtered_lines.append(line)
    return "\n".join(filtered_lines).strip()

class _State(TypedDict, total=False):
    llm: Any
    prompt: str
    cleaned_prompt: str
    raw_md: str
    final_md: str

def _build_graph():
    g = StateGraph(_State)

    def node_prepare(state: _State) -> _State:
        cleaned = _extract_sections_by_labels(state["prompt"])
        cleaned = _strip_assignment_lines_keep_canon(cleaned)
        state["cleaned_prompt"] = cleaned
        return state

    def node_generate(state: _State) -> _State:
        state["raw_md"] = _generate_markdown(state["llm"], state["cleaned_prompt"])
        return state

    def node_validate(state: _State) -> _State:
        state["final_md"] = _validate_or_repair(state["llm"], state["raw_md"], state["cleaned_prompt"])
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

def Full_Blog_Writer(prompt: str, temperature: float) -> Tuple[str, str]:
    llm = _make_llm(temperature=temperature, max_tokens=FULL_TEXT_MAX_TOKENS)
    out = _GRAPH.invoke({"llm": llm, "prompt": prompt})
    return prompt, out["final_md"]

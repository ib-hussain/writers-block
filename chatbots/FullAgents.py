# chatbots/FullAgents.py
from __future__ import annotations

import os
import json
import re
from typing import Tuple, Dict, Any, Optional

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

# Constraints (must match your requirement)
FULL_TEXT_MAX_TOKENS = 3584
FULL_TEXT_MIN_TOKENS = 1792

# Approx conversion: 1 token ~ 5 chars (matching your SingularAgents.py)
_CHARS_PER_TOKEN = 5

def _tok_to_char(n_tokens: int) -> int:
    return max(0, int(n_tokens) * _CHARS_PER_TOKEN)

FULL_MIN_CHARS = _tok_to_char(FULL_TEXT_MIN_TOKENS)
FULL_MAX_CHARS = _tok_to_char(FULL_TEXT_MAX_TOKENS)

# Model constraint: DeepSeek-V3 ONLY
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

# Labels used by your orchestrator in the Full prompt
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
# Draft extraction / cleaning
# ----------------------------
def _try_extract_content_md(maybe_json: str) -> Optional[str]:
    """
    If maybe_json is a JSON object with {"content_md": "..."} return that content.
    Otherwise None.
    """
    s = (maybe_json or "").strip()
    try:
        obj = json.loads(s)
        if isinstance(obj, dict) and isinstance(obj.get("content_md"), str):
            return obj["content_md"]
    except Exception:
        return None
    return None

def _extract_sections_by_labels(full_prompt: str) -> str:
    """
    Your orchestrator concatenates a prompt containing labeled agent blocks.
    Those blocks currently contain JSON from SingularAgents.

    This function:
    - finds each labeled block
    - extracts JSON and replaces it with content_md if possible
    - returns a 'cleaned' prompt suitable for the compiler model
    """
    if not full_prompt:
        return ""

    text = full_prompt

    # Build segments by scanning for known labels in order.
    # We do not assume perfect formatting; we search indexes.
    indices = []
    for label in _LABELS_IN_ORDER:
        idx = text.find(label)
        if idx != -1:
            indices.append((idx, label))
    if not indices:
        # No labels found; as a fallback, attempt to replace any standalone JSON objects that contain content_md.
        return _replace_any_json_objects(text)

    # Sort by position
    indices.sort(key=lambda x: x[0])

    # Determine span for each labeled content block
    cleaned = text
    # We replace from the end to preserve indices
    for i in range(len(indices) - 1, -1, -1):
        start_idx, label = indices[i]
        # content begins after label
        content_start = start_idx + len(label)
        # end is next label start or end of string
        end_idx = indices[i + 1][0] if i + 1 < len(indices) else len(text)

        block = text[content_start:end_idx].strip()

        extracted = _try_extract_content_md(block)
        if extracted is None:
            # If not JSON, keep as is.
            continue

        # Replace the block (not the label) with extracted content_md
        cleaned = cleaned[:content_start] + "\n" + extracted.strip() + "\n" + cleaned[end_idx:]

    # Additionally, handle any remaining JSON objects that include content_md
    cleaned = _replace_any_json_objects(cleaned)

    return cleaned

_JSON_OBJECT_PATTERN = re.compile(r"\{(?:[^{}]|(?R))*\}", re.DOTALL)

def _replace_any_json_objects(text: str) -> str:
    """
    Conservative pass: find JSON-like objects and replace those that parse and contain content_md.
    If parsing fails, keep original.
    """
    if not text:
        return ""

    # This recursive regex may not be supported in all Python builds; if it errors, skip safely.
    try:
        matches = list(_JSON_OBJECT_PATTERN.finditer(text))
    except Exception:
        return text

    if not matches:
        return text

    out = text
    for m in reversed(matches):
        s = m.group(0)
        content = _try_extract_content_md(s)
        if content is None:
            continue
        out = out[:m.start()] + content + out[m.end():]
    return out

# ----------------------------
# Generation + validation/repair
# ----------------------------
def _generate_markdown(llm: Together, prompt: str) -> str:
    messages = [
        SystemMessage(content=SYSTEM_DIRECTIVE_COMPILER),
        HumanMessage(content=prompt),
    ]
    out = llm.invoke(messages)
    return out.content if hasattr(out, "content") else str(out)

def _validate_or_repair(llm: Together, raw_md: str, cleaned_prompt: str) -> str:
    md = (raw_md or "").strip()

    # Basic hard constraints:
    # - no code fences
    # - within length budget (chars proxy)
    if "```" in md:
        # Repair to remove code fences
        repair_system = SYSTEM_DIRECTIVE_COMPILER + f"""
REPAIR MODE:
You produced output that violates constraints (e.g., code blocks).
Rewrite it as plain Markdown without code fences or HTML.
Keep the same meaning and structure.
Return Markdown only.
"""
        md = _generate_markdown(llm, f"{repair_system}\n\nORIGINAL_OUTPUT:\n{raw_md}\n\nSOURCE_PROMPT:\n{cleaned_prompt}")

    # Length handling
    ln = len(md)
    if ln > FULL_MAX_CHARS:
        # Trim by asking model to compress (prefer over naive slicing)
        compress_system = SYSTEM_DIRECTIVE_COMPILER + f"""
COMPRESSION MODE:
Your output is too long ({ln} chars). Rewrite it to fit within {FULL_MAX_CHARS} chars.
Keep key information, remove redundancy, shorten examples, tighten phrasing.
Return Markdown only.
"""
        md2 = _generate_markdown(llm, f"{compress_system}\n\nORIGINAL_OUTPUT:\n{md}\n\nSOURCE_PROMPT:\n{cleaned_prompt}")
        md2 = (md2 or "").strip()
        if md2:
            md = md2

        # If still too long, do a safe hard trim as last resort.
        if len(md) > FULL_MAX_CHARS:
            md = md[:FULL_MAX_CHARS].rstrip()

    elif ln < FULL_MIN_CHARS:
        # Expand by asking model to elaborate using only provided drafts (no new facts)
        expand_system = SYSTEM_DIRECTIVE_COMPILER + f"""
EXPANSION MODE:
Your output is too short ({ln} chars). Expand it to be at least {FULL_MIN_CHARS} chars.
Add helpful detail, clarifying sentences, and structure, but do NOT invent new facts.
Return Markdown only.
"""
        md2 = _generate_markdown(llm, f"{expand_system}\n\nORIGINAL_OUTPUT:\n{md}\n\nSOURCE_PROMPT:\n{cleaned_prompt}")
        md2 = (md2 or "").strip()
        if md2:
            md = md2

        # If still short, accept; do not loop repeatedly.

    return md.strip()

# ----------------------------
# LangGraph micro-graph: prepare -> generate -> validate/repair -> END
# ----------------------------
class _State(Dict[str, Any]):
    pass

def _build_graph():
    g = StateGraph(_State)

    def node_prepare(state: _State) -> _State:
        # Extract content_md from any JSON drafts inside the full prompt
        state["cleaned_prompt"] = _extract_sections_by_labels(state["prompt"])
        return state

    def node_generate(state: _State) -> _State:
        llm = state["llm"]
        # We feed the cleaned prompt to the compiler
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
    """
    Signature preserved: returns (used_prompt, output_markdown)

    Uses Together LLM with model deepseek-ai/DeepSeek-V3 only.
    Applies a micro-graph: prepare -> generate -> validate/repair.

    Constraints enforced:
    - max tokens: FULL_TEXT_MAX_TOKENS (via Together max_tokens)
    - length window: FULL_TEXT_MIN_TOKENS..FULL_TEXT_MAX_TOKENS (via char proxy)
    """
    llm = _make_llm(temperature=temperature, max_tokens=FULL_TEXT_MAX_TOKENS)
    state: _State = {"llm": llm, "prompt": prompt}
    out = _GRAPH.invoke(state)
    return prompt, out["final_md"]

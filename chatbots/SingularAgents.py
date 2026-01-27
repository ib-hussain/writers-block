# chatbots/SingularAgents.py
from __future__ import annotations

import os
import json
import time
import random
import threading
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

INTRO_MAX_TOKENS = 640
INTRO_MIN_TOKENS = 128

FINAL_CTA_MAX_TOKENS = 512
FINAL_CTA_MIN_TOKENS = 128

FAQ_MAX_TOKENS = 1024
FAQ_MIN_TOKENS = 512

BUISNESS_DESC_MAX_TOKENS = 1024
BUISNESS_DESC_MIN_TOKENS = 128

SHORT_CTA_MAX_TOKENS = 256
SHORT_CTA_MIN_TOKENS = 64

REFERENCES_MAX_TOKENS = 512
REFERENCES_MIN_TOKENS = 128

FULL_TEXT_MAX_TOKENS = 3584
FULL_TEXT_MIN_TOKENS = 1792

# Approx conversion: 1 token ~ 5 chars (coarse)
_CHARS_PER_TOKEN = 5

def _tok_to_char(n_tokens: int) -> int:
    return max(0, int(n_tokens) * _CHARS_PER_TOKEN)

SYSTEM_DIRECTIVE = """You are a section-writing sub-agent in a multi-agent pipeline.

HIGHEST PRIORITY RULES:
1) Output MUST be a SINGLE valid JSON object and NOTHING ELSE.
2) Do NOT wrap JSON in markdown fences.
3) JSON schema EXACTLY:
{
  "status": "ok" | "needs_review",
  "section_id": "<string>",
  "content_md": "<string markdown>",
  "warnings": ["<string>", "..."]
}
4) content_md must be compiler-safe markdown:
   - No HTML
   - No code blocks (``` or indentation-based)
   - No templating syntax
5) Do not reference other sections (no “as above/below”).
6) If information is missing, write best-effort and add a warning.

FORMAT EXAMPLE (follow exactly; return JSON only):
{
  "status": "ok",
  "section_id": "intro",
  "content_md": "## Heading\\nA direct answer in the first sentence.\\n\\nMore detail.",
  "warnings": []
}

Token discipline:
- Keep content_md concise and within the section's expected size.
"""

SECTION_SPECS: Dict[str, Dict[str, int]] = {
    "intro": {"min_chars": _tok_to_char(INTRO_MIN_TOKENS), "max_chars": _tok_to_char(INTRO_MAX_TOKENS)},
    "final_cta": {"min_chars": _tok_to_char(FINAL_CTA_MIN_TOKENS), "max_chars": _tok_to_char(FINAL_CTA_MAX_TOKENS)},
    "faqs": {"min_chars": _tok_to_char(FAQ_MIN_TOKENS), "max_chars": _tok_to_char(FAQ_MAX_TOKENS)},
    "business_description": {"min_chars": _tok_to_char(BUISNESS_DESC_MIN_TOKENS), "max_chars": _tok_to_char(BUISNESS_DESC_MAX_TOKENS)},
    "short_cta": {"min_chars": _tok_to_char(SHORT_CTA_MIN_TOKENS), "max_chars": _tok_to_char(SHORT_CTA_MAX_TOKENS)},
    "integrate_references": {"min_chars": _tok_to_char(REFERENCES_MIN_TOKENS), "max_chars": _tok_to_char(REFERENCES_MAX_TOKENS)},
}

# ----------------------------
# Thread-safe model alternation
# ----------------------------
_model_toggle_lock = threading.Lock()
_model_toggle_state: Dict[str, int] = {
    "intro": 0,
    "final_cta": 0,
    "faqs": 0,
    "business_description": 0,
    "integrate_references": 0,
}

def _choose_model(section_id: str, model_a: str, model_b: Optional[str]) -> str:
    if not model_b:
        return model_a
    with _model_toggle_lock:
        cur = _model_toggle_state.get(section_id, 0)
        _model_toggle_state[section_id] = 1 - cur
        return model_a if cur == 0 else model_b

# ----------------------------
# LLM factory
# ----------------------------
def _make_llm(temperature: float, max_tokens: int, model: str) -> Together:
    api_key = os.getenv("TOGETHER_API_KEY")
    if not api_key:
        raise RuntimeError("TOGETHER_API_KEY is not set in environment.")
    return Together(
        model=model,
        temperature=temperature,
        together_api_key=str(api_key),
        max_tokens=max_tokens,
    )

# ----------------------------
# Retry/backoff (Together transient failures)
# ----------------------------
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
            sleep_s = (0.4 * (2 ** i)) + random.uniform(0.0, 0.25)
            time.sleep(sleep_s)
    raise last_err  # pragma: no cover

# ----------------------------
# Generation + validation
# ----------------------------
def _generate_json(llm: Together, section_id: str, prompt: str) -> str:
    sys = SYSTEM_DIRECTIVE + f"\nSECTION_ID = {section_id}\n"
    messages = [SystemMessage(content=sys), HumanMessage(content=prompt)]
    return _invoke_with_retries(llm, messages, attempts=4)

def _try_parse_json(section_id: str, s: str) -> Optional[Dict[str, Any]]:
    try:
        obj = json.loads((s or "").strip())
        if not isinstance(obj, dict):
            return None

        required = {"status", "section_id", "content_md", "warnings"}
        if not required.issubset(obj.keys()):
            return None

        if obj.get("section_id") != section_id:
            obj["section_id"] = section_id

        if obj.get("status") not in ("ok", "needs_review"):
            obj["status"] = "needs_review"

        if not isinstance(obj.get("warnings"), list):
            obj["warnings"] = ["warnings field was not a list; normalised."]

        if not isinstance(obj.get("content_md"), str):
            return None

        return obj
    except Exception:
        return None

def _validate_or_repair(llm: Together, section_id: str, raw: str) -> str:
    spec = SECTION_SPECS.get(section_id, {"min_chars": 200, "max_chars": 1600})
    min_c, max_c = spec["min_chars"], spec["max_chars"]

    parsed = _try_parse_json(section_id, raw)
    if parsed is not None:
        ln = len(parsed["content_md"])
        if ln < min_c:
            parsed["warnings"].append(f"content_md shorter than target ({ln} < {min_c}).")
            parsed["status"] = "needs_review"
        if ln > max_c:
            parsed["content_md"] = parsed["content_md"][:max_c].rstrip()
            parsed["warnings"].append(f"content_md trimmed to max_chars={max_c}.")
            parsed["status"] = "needs_review"
        return json.dumps(parsed, ensure_ascii=False)

    # Repair attempt: IMPORTANT—use retries here as well
    repair_system = SYSTEM_DIRECTIVE + f"""
REPAIR MODE:
Convert the following INVALID output into a SINGLE valid JSON object matching the schema.
Preserve meaning. Do not add new facts. section_id must be "{section_id}".
Return JSON only.
"""
    messages = [
        SystemMessage(content=repair_system),
        HumanMessage(content=f"INVALID_OUTPUT:\n{raw}")
    ]
    repaired_text = _invoke_with_retries(llm, messages, attempts=3)

    parsed2 = _try_parse_json(section_id, repaired_text)
    if parsed2 is None:
        fallback = {
            "status": "needs_review",
            "section_id": section_id,
            "content_md": "",
            "warnings": ["LLM output could not be repaired into valid JSON."],
        }
        return json.dumps(fallback, ensure_ascii=False)

    ln2 = len(parsed2["content_md"])
    if ln2 < min_c:
        parsed2["warnings"].append(f"content_md shorter than target ({ln2} < {min_c}).")
        parsed2["status"] = "needs_review"
    if ln2 > max_c:
        parsed2["content_md"] = parsed2["content_md"][:max_c].rstrip()
        parsed2["warnings"].append(f"content_md trimmed to max_chars={max_c}.")
        parsed2["status"] = "needs_review"

    return json.dumps(parsed2, ensure_ascii=False)

# ----------------------------
# LangGraph micro-graph: generate -> validate -> END
# ----------------------------
class _State(TypedDict, total=False):
    llm: Any
    section_id: str
    prompt: str
    raw: str
    final_json: str

def _build_graph():
    g = StateGraph(_State)

    def node_generate(state: _State) -> _State:
        state["raw"] = _generate_json(state["llm"], state["section_id"], state["prompt"])
        return state

    def node_validate(state: _State) -> _State:
        state["final_json"] = _validate_or_repair(state["llm"], state["section_id"], state["raw"])
        return state

    g.add_node("generate", node_generate)
    g.add_node("validate", node_validate)
    g.set_entry_point("generate")
    g.add_edge("generate", "validate")
    g.add_edge("validate", END)
    return g.compile()

_GRAPH = _build_graph()

def _run_section_agent(
    section_id: str,
    prompt: str,
    temperature: float,
    model: str,
    max_tokens: int,
    fallback_model: Optional[str] = None
) -> Tuple[str, str]:
    """
    Run section agent. If transient provider failures occur, retry on the same model,
    then optionally try fallback_model (still within your allowed set).
    """
    llm = _make_llm(temperature=temperature, max_tokens=max_tokens, model=model)
    state: _State = {"llm": llm, "section_id": section_id, "prompt": prompt}

    try:
        out = _GRAPH.invoke(state)
        return prompt, out["final_json"]
    except Exception as e:
        if (not _is_transient_provider_error(str(e))) or (not fallback_model) or (fallback_model == model):
            raise

        llm2 = _make_llm(temperature=temperature, max_tokens=max_tokens, model=fallback_model)
        state2: _State = {"llm": llm2, "section_id": section_id, "prompt": prompt}
        out2 = _GRAPH.invoke(state2)
        return prompt, out2["final_json"]

# ----------------------------
# Public agent functions (signature preserved, models unchanged)
# ----------------------------
def Intro_Writing_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    model_a = "Qwen/Qwen3-Next-80B-A3B-Instruct"
    model_b = "deepseek-ai/DeepSeek-R1-0528-tput"
    model = _choose_model("intro", model_a=model_a, model_b=model_b)
    fallback = model_b if model == model_a else model_a
    return _run_section_agent("intro", prompt, temperature, model=model, max_tokens=INTRO_MAX_TOKENS, fallback_model=fallback)

def Final_CTA_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    model_a = "openai/gpt-oss-120b"
    model_b = "meta-llama/Meta-Llama-3-8B-Instruct-Lite"
    model = _choose_model("final_cta", model_a=model_a, model_b=model_b)
    fallback = model_b if model == model_a else model_a
    return _run_section_agent("final_cta", prompt, temperature, model=model, max_tokens=FINAL_CTA_MAX_TOKENS, fallback_model=fallback)

def FAQs_Writing_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    model_a = "deepseek-ai/DeepSeek-V3.1"
    model_b = "Qwen/Qwen2.5-72B-Instruct-Turbo"
    model = _choose_model("faqs", model_a=model_a, model_b=model_b)
    fallback = model_b if model == model_a else model_a
    return _run_section_agent("faqs", prompt, temperature, model=model, max_tokens=FAQ_MAX_TOKENS, fallback_model=fallback)

def Business_Description_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    model_a = "Qwen/Qwen3-Next-80B-A3B-Instruct"
    model_b = "Qwen/Qwen2.5-7B-Instruct-Turbo"
    model = _choose_model("business_description", model_a=model_a, model_b=model_b)
    fallback = model_b if model == model_a else model_a
    return _run_section_agent("business_description", prompt, temperature, model=model, max_tokens=BUISNESS_DESC_MAX_TOKENS, fallback_model=fallback)

def Short_CTA_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    return _run_section_agent(
        "short_cta",
        prompt,
        temperature,
        model="google/gemma-3n-E4B-it",
        max_tokens=SHORT_CTA_MAX_TOKENS,
        fallback_model=None
    )

def References_Writing_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    model_a = "openai/gpt-oss-120b"
    model_b = "OpenAI/gpt-oss-20B"
    model = _choose_model("integrate_references", model_a=model_a, model_b=model_b)
    fallback = model_b if model == model_a else model_a
    return _run_section_agent("integrate_references", prompt, temperature, model=model, max_tokens=REFERENCES_MAX_TOKENS, fallback_model=fallback)

# chatbots/SingularAgents.py
from __future__ import annotations
import os
from typing import Tuple, Dict, Any
import json
from langchain_openai import ChatOpenAI
from typing import Dict, Any, Optional
from langchain_together import Together
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END

# DEFINE CONSTANTS AND CONFIG
DEBUGGING_MODE = True
NULL_STRING = " "
POOL_MIN = 1
POOL_MAX = 10
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
SYSTEM_DIRECTIVE = """You are a section-writing sub-agent in a multi-agent pipeline.

        HIGHEST PRIORITY RULES:
        - Output MUST be a SINGLE valid JSON object and NOTHING ELSE.
        - Do NOT wrap JSON in markdown fences.
        - JSON schema:
        {
        "status": "ok" | "needs_review",
        "section_id": string,
        "content_md": string,
        "warnings": [string]
        }
        - content_md must be compiler-safe markdown: no HTML, no code blocks, no templating syntax.
        - Do not reference other sections (no “as above/below”).
        - If information is missing, write best-effort and add a warning.

        Token discipline:
        - Keep content_md concise and within the section's expected size.
        """

# Per-section constraints 
SECTION_SPECS: Dict[str, Dict[str, Any]] = {
    "intro": {"min_chars": INTRO_MIN_TOKENS, "max_chars": INTRO_MAX_TOKENS},
    "final_cta": {"min_chars": FINAL_CTA_MIN_TOKENS, "max_chars": FINAL_CTA_MAX_TOKENS},
    "faqs": {"min_chars": FAQ_MIN_TOKENS, "max_chars": FAQ_MAX_TOKENS},
    "business_description": {"min_chars": BUISNESS_DESC_MIN_TOKENS, "max_chars": BUISNESS_DESC_MAX_TOKENS},
    "short_cta": {"min_chars": SHORT_CTA_MIN_TOKENS, "max_chars": SHORT_CTA_MAX_TOKENS},
    "integrate_references": {"min_chars": REFERENCES_MIN_TOKENS, "max_chars": REFERENCES_MAX_TOKENS},
}
def _make_llm(temperature: float) -> Together:
    # Choose your model here; keep it stable.
    # return ChatOpenAI(
    #     model="gpt-4o-mini",
    #     temperature=temperature,
    #     max_tokens=640,
    #     timeout=60,
    #     max_retries=2,
    # )
    llm = Together(
        model="google/gemma-3n-E4B-it",
        temperature=temperature,
        together_api_key=str(os.getenv("TOGETHER_API_KEY"))
    )
    return llm

def _infer_section_id(default_section: str, prompt: str) -> str:
    # Orchestrator already knows which function it called; keep this simple.
    return default_section

def _generate_json(llm: Together, section_id: str, prompt: str) -> str:
    sys = SYSTEM_DIRECTIVE + f"\nSECTION_ID = {section_id}\n"
    messages = [SystemMessage(content=sys), HumanMessage(content=prompt)]
    out = llm.invoke(messages)
    return out.content if hasattr(out, "content") else str(out)

def _validate_or_repair(llm: Together, section_id: str, raw: str) -> str:
    spec = SECTION_SPECS.get(section_id, {"min_chars": 200, "max_chars": 1600})
    min_c, max_c = spec["min_chars"], spec["max_chars"]

    def try_parse(s: str) -> Dict[str, Any] | None:
        try:
            obj = json.loads(s.strip())
            if not isinstance(obj, dict):
                return None
            if "status" not in obj or "section_id" not in obj or "content_md" not in obj or "warnings" not in obj:
                return None
            if obj["section_id"] != section_id:
                # force exact section id
                obj["section_id"] = section_id
            if not isinstance(obj["warnings"], list):
                obj["warnings"] = ["warnings field was not a list; normalised."]
            if not isinstance(obj["content_md"], str):
                return None
            # size check
            ln = len(obj["content_md"])
            if ln < min_c:
                obj["warnings"].append(f"content_md shorter than target ({ln} < {min_c}).")
            if ln > max_c:
                # hard trim (compiler-safe)
                obj["content_md"] = obj["content_md"][:max_c].rstrip()
                obj["warnings"].append(f"content_md trimmed to max_chars={max_c}.")
            return obj
        except Exception:
            return None

    parsed = try_parse(raw)
    if parsed is not None:
        return json.dumps(parsed, ensure_ascii=False)

    # One repair attempt
    repair_system = SYSTEM_DIRECTIVE + f"""
REPAIR MODE:
You will be given invalid output. Convert it into a SINGLE valid JSON object matching the schema exactly.
Preserve meaning. Do not add new facts. section_id must be "{section_id}".
Return JSON only.
"""
    messages = [
        SystemMessage(content=repair_system),
        HumanMessage(content=f"INVALID_OUTPUT:\n{raw}")
    ]
    repaired = llm.invoke(messages)
    repaired_text = repaired.content if hasattr(repaired, "content") else str(repaired)

    parsed2 = try_parse(repaired_text)
    if parsed2 is None:
        # last resort deterministic fallback
        fallback = {
            "status": "needs_review",
            "section_id": section_id,
            "content_md": "",
            "warnings": ["LLM output could not be repaired into valid JSON."],
        }
        return json.dumps(fallback, ensure_ascii=False)

    return json.dumps(parsed2, ensure_ascii=False)

# ----------------------------
# LangGraph micro-graph: generate -> validate/repair -> END
# ----------------------------
class _State(Dict[str, Any]):
    pass

def _build_graph():
    g = StateGraph(_State)

    def node_generate(state: _State) -> _State:
        llm = state["llm"]
        section_id = state["section_id"]
        prompt = state["prompt"]
        state["raw"] = _generate_json(llm, section_id, prompt)
        return state

    def node_validate(state: _State) -> _State:
        llm = state["llm"]
        section_id = state["section_id"]
        state["final_json"] = _validate_or_repair(llm, section_id, state["raw"])
        return state

    g.add_node("generate", node_generate)
    g.add_node("validate", node_validate)
    g.set_entry_point("generate")
    g.add_edge("generate", "validate")
    g.add_edge("validate", END)

    return g.compile()

_GRAPH = _build_graph()

def _run_section_agent(section_id: str, prompt: str, temperature: float) -> Tuple[str, str]:
    llm = _make_llm(temperature)
    state: _State = {"llm": llm, "section_id": section_id, "prompt": prompt}
    out = _GRAPH.invoke(state)
    return prompt, out["final_json"]

# ----------------------------
# Public agent functions (signature preserved)
# ----------------------------
def Intro_Writing_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    return _run_section_agent("intro", prompt, temperature)

def Final_CTA_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    return _run_section_agent("final_cta", prompt, temperature)

def FAQs_Writing_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    return _run_section_agent("faqs", prompt, temperature)

def Business_Description_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    return _run_section_agent("business_description", prompt, temperature)

def Short_CTA_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    return _run_section_agent("short_cta", prompt, temperature)

def References_Writing_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    return _run_section_agent("integrate_references", prompt, temperature)

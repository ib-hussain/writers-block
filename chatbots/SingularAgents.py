# chatbots/SingularAgents.py
from __future__ import annotations

import os
import re
import time
import random
import threading
from typing import Tuple, Optional, Dict, Any, List

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_together import Together

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# ============================================================
# CONFIG
# ============================================================
DEBUGGING_MODE = True

INTRO_MAX_TOKENS = 640
FINAL_CTA_MAX_TOKENS = 512
FAQ_MAX_TOKENS = 1024
BUSINESS_DESC_MAX_TOKENS = 768
SHORT_CTA_MAX_TOKENS = 256
REFERENCES_MAX_TOKENS = 512

MAX_ATTEMPTS = 4
BASE_BACKOFF_S = 0.6


# ============================================================
# GUARDRAILS
# ============================================================
_COMMON_GUARDRAILS = """GLOBAL RULES (MANDATORY):
- Output MUST be plain Markdown ONLY (single string).
- Do NOT output JSON.
- Do NOT output code fences (```), HTML tags, or XML.
- Do NOT include meta commentary (e.g., "Here is...", "Assistant:", "Response:").
- Do NOT include variable assignment lines (e.g., "COMPANY_NAME = ...").
- Preserve placeholders exactly as-is when they appear in the prompt:
  {COMPANY_NAME}, {CALL_NUMBER}, {ADDRESS}, {LINK}, {STATE_NAME}, {COMPANY_EMPLOYEE}.
- Do NOT invent legal/medical specifics:
  - No statute numbers, filing deadlines, coverage limits, policy limits, jurisdiction rules, or medical claims
    unless explicitly present in the prompt.
- If you are unsure, stay general and practical; do NOT hallucinate.
"""

_SECTION_SYSTEM: Dict[str, str] = {
    "intro": f"""You write blog introductions for legal/health businesses.
{_COMMON_GUARDRAILS}

SECTION RULES:
- 1–2 short paragraphs.
- Must be aligned to the user message and business context in the prompt.
- Hook + promise: tell the reader what they will learn.
- Keep it concrete. No drifting to unrelated topics.
""",

    "final_cta": f"""You write the FINAL Call-To-Action for a legal/health blog.
{_COMMON_GUARDRAILS}

SECTION RULES:
- Start with a heading (## or ###).
- 1–2 short paragraphs.
- Clear next step (consultation / call / visit) using placeholders if present.
- No exaggerated claims ("guarantee", "best", "win every case") unless provided.
""",

    "faqs": f"""You write an FAQ section for a legal/health blog.
{_COMMON_GUARDRAILS}

SECTION RULES:
- 4–7 Q/A pairs.
- Each question as a subheading: "### Question?"
- Each answer: 1–3 sentences; must start with a direct answer.
- If the prompt contains explicit FAQ questions, answer those. Otherwise, generate relevant FAQs from the user message.
""",

    "business_description": f"""You write a business description block for the company.
{_COMMON_GUARDRAILS}

SECTION RULES:
- Heading: "## About {{COMPANY_NAME}}" OR "## About the Firm" (use placeholders if provided).
- 1–2 paragraphs only.
- Mention location/state and what the company helps with, based on prompt.
- Keep it credible, specific, and aligned to the blog topic.
""",

    "short_cta": f"""You write a SHORT CTA snippet that fits mid-article.
{_COMMON_GUARDRAILS}

SECTION RULES:
- 1–2 very short sentences (or 2 short lines).
- Encourage a consultation/contact.
- Do NOT include phone/address unless the prompt explicitly requires it.
""",

    "integrate_references": f"""You write a references/resources block.
{_COMMON_GUARDRAILS}

SECTION RULES:
- Output a section:
  "## References" then 3–6 bullet points.
- If prompt provides a {{SOURCE}} or reference hints, use them.
- If no sources are provided, output generic credible source CATEGORIES (no fabricated URLs):
  e.g., "State health department guidance", "CDC / NIH topic page", "Insurance policy documents".
- Do NOT invent URLs, statute numbers, case citations, or journal articles.
""",
}


# ============================================================
# ROUND-ROBIN MODEL CHOICE (A/B)
# ============================================================
_model_toggle_lock = threading.Lock()
_model_toggle_state: Dict[str, int] = {}


def _choose_model(section_id: str, model_a: str, model_b: str) -> str:
    with _model_toggle_lock:
        cur = _model_toggle_state.get(section_id, 0)
        _model_toggle_state[section_id] = 1 - cur
        return model_a if cur == 0 else model_b


# ============================================================
# LLM WRAPPER
# ============================================================
def _make_llm(model: str, temperature: float, max_tokens: int) -> Together:
    api_key = os.getenv("TOGETHER_API_KEY") or os.getenv("TOGETHERAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing TOGETHER_API_KEY in environment.")

    # Handle different param names across versions
    try:
        return Together(model=model, temperature=temperature, max_tokens=max_tokens, api_key=api_key)
    except TypeError:
        return Together(model=model, temperature=temperature, max_tokens=max_tokens, together_api_key=api_key)


def _is_transient_error(e: Exception) -> bool:
    msg = str(e).lower()
    transient = [
        "timeout", "timed out", "temporarily", "rate limit", "429",
        "connection", "disconnect", "overloaded", "try again",
        "bad gateway", "502", "503", "504",
        "server closed the connection unexpectedly",
    ]
    return any(x in msg for x in transient)


def _invoke_with_retries(llm: Together, system_text: str, user_text: str, section_id: str) -> str:
    last: Optional[Exception] = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            t0 = time.time()
            out = llm.invoke([SystemMessage(content=system_text), HumanMessage(content=user_text)])

            if isinstance(out, str):
                raw = out
            elif hasattr(out, "content"):
                raw = out.content or ""
            else:
                raw = str(out)

            dt = (time.time() - t0) * 1000
            if DEBUGGING_MODE:
                print(f"[SingularAgents] {section_id} ok | attempt={attempt} | {dt:.0f}ms | chars={len(raw)}")
            return raw

        except Exception as e:
            last = e
            if DEBUGGING_MODE:
                print(f"[SingularAgents] {section_id} fail | attempt={attempt}/{MAX_ATTEMPTS} | err={e}")
            if attempt == MAX_ATTEMPTS or not _is_transient_error(e):
                break
            time.sleep(BASE_BACKOFF_S * attempt + random.random() * 0.6)

    raise RuntimeError(f"{section_id} failed after {MAX_ATTEMPTS} attempts: {last}")


# ============================================================
# CLEANING + VALIDATION
# ============================================================
_TAG_BLOCK_RE = re.compile(r"<<[A-Z0-9_]+>>\n[\s\S]*?(?=\n<<[A-Z0-9_]+>>\n|\Z)", re.S)


def _strip_outer_quotes(t: str) -> str:
    t = (t or "").strip()
    if len(t) >= 2 and ((t[0] == '"' and t[-1] == '"') or (t[0] == "'" and t[-1] == "'")):
        return t[1:-1].strip()
    return t


def _clean_output(text: str) -> str:
    if not text:
        return ""

    t = text.strip()
    t = re.sub(r"```[\s\S]*?```", "", t).strip()
    t = re.sub(r"^(assistant|response|output|answer)\s*:\s*", "", t, flags=re.I).strip()
    t = re.sub(r"^ASSISTANT[’']?S OUTPUT.*?:\s*", "", t, flags=re.I).strip()
    t = re.sub(r"^\s*[A-Z_]{3,}\s*=\s*.*$", "", t, flags=re.M).strip()
    t = re.sub(_TAG_BLOCK_RE, "", t).strip()
    t = _strip_outer_quotes(t)
    return t.strip()


def _looks_invalid(section_id: str, text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if "```" in t:
        return True
    if t.startswith("{") or t.startswith("["):
        return True
    if t.lower().startswith(("assistant:", "response:", "output:")):
        return True

    if section_id == "faqs" and t.count("###") < 2:
        return True
    if section_id == "final_cta" and not (t.startswith("##") or t.startswith("###")):
        return True

    return False


def _repair_prompt(user_prompt: str, bad_output: str) -> str:
    return (
        "Your previous output was empty or violated the rules.\n"
        "Rewrite it STRICTLY following the section rules.\n"
        "- Output Markdown only\n"
        "- No meta commentary\n"
        "- No JSON\n"
        "- Do not echo the prompt\n\n"
        "ORIGINAL PROMPT:\n"
        f"{user_prompt}\n\n"
        "BAD OUTPUT:\n"
        f"{bad_output}\n"
    )


def _fallback(section_id: str) -> str:
    if section_id == "intro":
        return (
            "Injuries and accidents can create sudden costs and stress. This article explains what to do next and what to document.\n\n"
            "You will learn practical steps, key evidence, and how to avoid common mistakes."
        )
    if section_id == "final_cta":
        return (
            "## Get a Consultation\n"
            "If you are facing bills, paperwork, or disputes, get guidance early.\n\n"
            "Contact us to discuss your situation and your next steps."
        )
    if section_id == "faqs":
        return (
            "### What should I do first?\n"
            "Start by getting help and documenting what happened. Keep records organised.\n\n"
            "### What evidence matters most?\n"
            "Medical records, photos, and witness details help. Save everything with dates.\n\n"
            "### How long does the process take?\n"
            "It depends on complexity and cooperation. Early action helps timelines.\n\n"
            "### When should I speak to a professional?\n"
            "Speak early if costs are high or there is a dispute. It prevents delays."
        )
    if section_id == "business_description":
        return (
            "## About {COMPANY_NAME}\n"
            "{COMPANY_NAME} helps clients understand their options and move forward with confidence. "
            "We focus on careful documentation, clear advice, and practical support.\n\n"
            "Contact us if you want a clear plan and realistic next steps."
        )
    if section_id == "short_cta":
        return "If you need clarity, reach out for a consultation. Early guidance can protect your position."
    if section_id == "integrate_references":
        return (
            "## References\n"
            "- Government guidance relevant to the topic\n"
            "- CDC/NIH topic pages (health)\n"
            "- Insurance policy documents and claim forms\n"
            "- Hospital/clinic discharge instructions and follow-up guidance"
        )
    return ""


# ============================================================
# SECTION RUNNER (WITH FALLBACK MODEL)
# ============================================================
def _run_section_agent(
    section_id: str,
    prompt: str,
    temperature: float,
    model: str,
    max_tokens: int,
    fallback_model: Optional[str] = None,
) -> Tuple[str, str]:
    sys = _SECTION_SYSTEM[section_id]

    def _run_once(m: str) -> str:
        llm = _make_llm(model=m, temperature=temperature, max_tokens=max_tokens)
        raw = _invoke_with_retries(llm, sys, prompt, section_id)
        cleaned = _clean_output(raw)

        if _looks_invalid(section_id, cleaned):
            if DEBUGGING_MODE:
                print(f"[SingularAgents] {section_id} invalid -> repair pass | model={m} | chars={len(cleaned)}")
            repair_user = _repair_prompt(prompt, cleaned)
            raw2 = _invoke_with_retries(llm, sys, repair_user, section_id)
            cleaned2 = _clean_output(raw2)
            if not _looks_invalid(section_id, cleaned2):
                cleaned = cleaned2

        return cleaned.strip()

    # Try primary
    out = ""
    primary_err: Optional[Exception] = None
    t0 = time.time()

    try:
        out = _run_once(model)
    except Exception as e:
        primary_err = e
        out = ""

    # If empty/invalid and fallback exists, try fallback once
    if (not out) and fallback_model:
        if DEBUGGING_MODE:
            print(f"[SingularAgents] {section_id} switching fallback model -> {fallback_model} | primary_err={primary_err}")
        try:
            out = _run_once(fallback_model)
        except Exception as e2:
            if DEBUGGING_MODE:
                print(f"[SingularAgents] {section_id} fallback also failed: {e2}")
            out = ""

    if not out:
        out = _fallback(section_id)

    dt = (time.time() - t0) * 1000
    if DEBUGGING_MODE:
        print(f"[SingularAgents] {section_id} final | {dt:.0f}ms | chars={len(out)} | model={model}")

    return prompt, out.strip()


# ============================================================
# PUBLIC AGENTS (YOUR MODEL A/B LISTS)
# ============================================================
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
    return _run_section_agent("business_description", prompt, temperature, model=model, max_tokens=BUSINESS_DESC_MAX_TOKENS, fallback_model=fallback)


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
    model_a = "openai/gpt-oss-20B"
    model_b = "openai/gpt-oss-120b"
    model = _choose_model("integrate_references", model_a=model_a, model_b=model_b)
    fallback = model_b if model == model_a else model_a
    return _run_section_agent("integrate_references", prompt, temperature, model=model, max_tokens=REFERENCES_MAX_TOKENS, fallback_model=fallback)

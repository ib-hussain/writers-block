# chatbots/SingularAgents.py
from __future__ import annotations
import os
import re
import time
import random
import threading
from typing import Tuple, Optional, List
from langchain_together import Together
from langchain_core.messages import SystemMessage, HumanMessage

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# CONFIG
DEBUGGING_MODE = True

INTRO_MAX_TOKENS = 640
FINAL_CTA_MAX_TOKENS = 512
FAQ_MAX_TOKENS = 1024
BUSINESS_DESC_MAX_TOKENS = 768
SHORT_CTA_MAX_TOKENS = 256
REFERENCES_MAX_TOKENS = 512

MAX_ATTEMPTS = 4
BASE_BACKOFF_S = 0.6

# Regex patterns
_TAG_BLOCK_RE = re.compile(r"<<[A-Z0-9_]+>>\n[\s\S]*?(?=\n<<[A-Z0-9_]+>>\n|\Z)")

# GUARDRAILS
_COMMON_GUARDRAILS = """GLOBAL RULES (MANDATORY):
- Output MUST be plain Markdown ONLY.
- Do NOT include meta commentary (e.g., "Here is...", "Assistant:", "Response:").
- Do NOT include variable assignment lines (e.g., "COMPANY_NAME = ...").
- Preserve placeholders exactly as-is when they appear in the prompt:
  {COMPANY_NAME}, {CALL_NUMBER}, {ADDRESS}, {LINK}, {STATE_NAME}, {COMPANY_EMPLOYEE}.
- Do NOT invent legal/medical specifics.
- If you are unsure, stay general and practical; do NOT hallucinate, do NOT MAKE MISTAKES.
"""

# LLM WRAPPER
def _make_llm(model: str, temperature: float, max_tokens: int) -> Together:
    api_key = os.getenv("TOGETHER_API_KEY") or os.getenv("TOGETHERAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing TOGETHER_API_KEY in environment.")
    # Handle different param names across versions
    try:
        return Together(model=model, temperature=temperature, max_tokens=max_tokens, api_key=api_key)
    except Exception as ebc:
        # Try alternative parameter names for different versions
        try:
            return Together(model=model, temperature=temperature, max_tokens=max_tokens, together_api_key=api_key)
        except Exception:
            raise RuntimeError(f"Failed to create LLM instance: {ebc}")

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
            if attempt > 1:
                # Exponential backoff with jitter
                backoff = BASE_BACKOFF_S * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                time.sleep(backoff)
                
                if DEBUGGING_MODE:
                    print(f"[SingularAgents] {section_id} retry {attempt}/{MAX_ATTEMPTS} after {backoff:.2f}s")
            
            # Create messages
            messages = [
                SystemMessage(content=system_text),
                HumanMessage(content=user_text)
            ]
            
            # Invoke LLM
            response = llm.invoke(messages)
            
            # Extract content
            if hasattr(response, 'content'):
                content = response.content
            elif isinstance(response, str):
                content = response
            elif hasattr(response, '__str__'):
                content = str(response)
            else:
                content = ""
            
            if content and content.strip():
                if DEBUGGING_MODE:
                    print(f"[SingularAgents] {section_id} attempt {attempt} successful")
                return content
                
        except Exception as e:
            last = e
            if DEBUGGING_MODE:
                print(f"[SingularAgents] {section_id} attempt {attempt} failed: {e}")
            
            # If not transient error, break early
            if not _is_transient_error(e) and attempt < MAX_ATTEMPTS:
                break
    
    # If all attempts failed
    if last:
        raise RuntimeError(f"{section_id} failed after {MAX_ATTEMPTS} attempts: {last}")
    else:
        raise RuntimeError(f"{section_id} failed: No valid response received")

# CLEANING + VALIDATION
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

def _run_once(
    prompt: str,
    temperature: float,
    model: str,
    max_tokens: int,
    system_text: str
) -> str:
    llm = _make_llm(model=model, temperature=temperature, max_tokens=max_tokens)
    raw = _invoke_with_retries(llm, system_text=system_text, user_text=prompt, section_id=model)
    cleaned = _clean_output(raw)
    return cleaned.strip()

def _choose_model(section_id: str, model_a: str, model_b: str) -> str:
    """Simple round-robin model selection"""
    # Create a simple deterministic choice based on section_id
    hash_val = hash(section_id) % 2
    return model_a if hash_val == 0 else model_b

# SECTION RUNNER (WITH FALLBACK MODEL)
def _run_section_agent(
    section_id: str,
    prompt: str,
    temperature: float,
    model: str,
    max_tokens: int,
    fallback_model: Optional[str] = None,
) -> str:

    # Try primary
    out = ""
    primary_err: Optional[Exception] = None
    t0 = time.time()

    try:
        out = _run_once(prompt, temperature, model, max_tokens, _COMMON_GUARDRAILS)
    except Exception as e:
        primary_err = e
        if DEBUGGING_MODE:
            print(f"[SingularAgents] {section_id} primary model {model} failed: {e}")

    # If empty/invalid and fallback exists, try fallback once
    if (not out or out.strip() == "") and fallback_model:
        if DEBUGGING_MODE: 
            print(f"[SingularAgents] {section_id} switching to fallback model -> {fallback_model} | primary_err={primary_err}")
        try: 
            out = _run_once(prompt, temperature, fallback_model, max_tokens, _COMMON_GUARDRAILS)
        except Exception as e2:
            if DEBUGGING_MODE:
                print(f"[SingularAgents] {section_id} fallback also failed: {e2}")
            out = f"[SingularAgents] {section_id} ERROR: Both models failed"

    dt = (time.time() - t0) * 1000
    if DEBUGGING_MODE: 
        print(f"[SingularAgents] {section_id} final | {dt:.0f}ms | chars={len(out)} | model={model}")
    return out.strip()


# PUBLIC AGENTS (YOUR MODEL A/B LISTS)
def Intro_Writing_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    model_a = "Qwen/Qwen3-Next-80B-A3B-Instruct"
    model_b = "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8" #"deepseek-ai/DeepSeek-R1-0528-tput" #commenting out deepseek models
    model = _choose_model("intro", model_a=model_a, model_b=model_b)
    fallback = model_b if model == model_a else model_a
    content = _run_section_agent("intro", prompt, temperature, model=model, 
                               max_tokens=INTRO_MAX_TOKENS, fallback_model=fallback)
    return prompt, content

def Final_CTA_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    model_a = "openai/gpt-oss-120b"
    model_b = "meta-llama/Meta-Llama-3-8B-Instruct-Lite"
    model = _choose_model("final_cta", model_a=model_a, model_b=model_b)
    fallback = model_b if model == model_a else model_a
    content = _run_section_agent("final_cta", prompt, temperature, model=model, 
                               max_tokens=FINAL_CTA_MAX_TOKENS, fallback_model=fallback)
    return prompt, content

def FAQs_Writing_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    model_a = "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"#"deepseek-ai/DeepSeek-V3.1"
    model_b = "Qwen/Qwen2.5-72B-Instruct-Turbo"
    model = _choose_model("faqs", model_a=model_a, model_b=model_b)
    fallback = model_b if model == model_a else model_a
    content = _run_section_agent("faqs", prompt, temperature, model=model, 
                               max_tokens=FAQ_MAX_TOKENS, fallback_model=fallback)
    return prompt, content

def Business_Description_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    model_a = "Qwen/Qwen3-Next-80B-A3B-Instruct"
    model_b = "Qwen/Qwen2.5-7B-Instruct-Turbo"
    model = _choose_model("business_description", model_a=model_a, model_b=model_b)
    fallback = model_b if model == model_a else model_a
    content = _run_section_agent("business_description", prompt, temperature, model=model, 
                               max_tokens=BUSINESS_DESC_MAX_TOKENS, fallback_model=fallback)
    return prompt, content

def Short_CTA_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    content = _run_section_agent(
        "short_cta",
        prompt,
        temperature,
        model="google/gemma-3n-E4B-it",
        max_tokens=SHORT_CTA_MAX_TOKENS,
        fallback_model=None
    )
    return prompt, content

def References_Writing_Agent(prompt: str, temperature: float) -> Tuple[str, str]:
    model_a = "OpenAI/gpt-oss-20B"
    model_b = "openai/gpt-oss-120b"
    model = _choose_model("integrate_references", model_a=model_a, model_b=model_b)
    fallback = model_b if model == model_a else model_a
    content = _run_section_agent("integrate_references", prompt, temperature, model=model, 
                               max_tokens=REFERENCES_MAX_TOKENS, fallback_model=fallback)
    return prompt, content
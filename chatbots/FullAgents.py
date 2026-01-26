# chatbots/FullAgents.py
from __future__ import annotations
from typing import Tuple, Dict, Any
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass
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



SYSTEM_DIRECTIVE_COMPILER = """You are the final compiler agent.

HIGHEST PRIORITY RULES:
- Output MUST be plain Markdown (NOT JSON).
- Do not invent facts beyond what the user message or section drafts provide.
- Preserve placeholders exactly as-is (e.g., COMPANY_NAME, CALL_NUMBER if present in the drafts).
- Remove repetition, normalise tone, and ensure the final blog reads as one coherent piece.
"""

def _make_llm(temperature: float) -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=max(0.1, min(temperature, 0.6)),  # compiler should be steadier
        max_tokens=900,  # compiler output can be longer; tune as needed
        timeout=60,
        max_retries=2,
    )

def _extract_content(label: str, maybe_json: str) -> str:
    s = (maybe_json or "").strip()
    try:
        obj = json.loads(s)
        if isinstance(obj, dict) and "content_md" in obj:
            return obj["content_md"] or ""
    except Exception:
        pass
    # If it wasn't JSON, treat as raw markdown
    return s

def Full_Blog_Writer(prompt: str, temperature: float) -> Tuple[str, str]:
    """
    Signature preserved: (used_prompt, output)
    Expects prompt to contain the concatenated section outputs.
    If those outputs are JSON from section agents, we extract content_md.
    """
    # model = deepseek-ai/DeepSeek-V3
    # Heuristic extraction: your prompt labels sections with lines like "Introduction Agent:"
    # We will not attempt complex parsing—just ask the model to treat embedded JSON as drafts.
    llm = _make_llm(temperature)

    messages = [
        SystemMessage(content=SYSTEM_DIRECTIVE_COMPILER),
        HumanMessage(content=prompt),
    ]
    out = llm.invoke(messages)
    return prompt, (out.content if hasattr(out, "content") else str(out))

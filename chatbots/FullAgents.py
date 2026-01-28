# chatbots/FullAgents.py
from __future__ import annotations

import os
import time
import random
import re
from typing import Tuple, Optional, Any, List, Dict

from langchain_together import Together
from langchain_core.messages import SystemMessage, HumanMessage

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

DEBUGGING_MODE = True

# Compiler model
COMPILER_MODEL = "deepseek-ai/DeepSeek-V3"
FULL_TEXT_MAX_TOKENS = 3584


# ----------------------------
# STRICT COMPILER DIRECTIVE
# ----------------------------
SYSTEM_DIRECTIVE_COMPILER = """You are the final compiler agent for a business blog article.

CRITICAL OUTPUT RULES:
1) Output MUST be plain Markdown ONLY (a single string).
2) Do NOT output JSON, code fences (```), HTML tags, XML, or templating syntax.
3) Do NOT include variable assignment lines (e.g., "COMPANY_NAME = ...").
4) Preserve placeholders exactly as-is (COMPANY_NAME, CALL_NUMBER, LINK, ADDRESS, STATE_NAME, etc.).
5) Do NOT add new legal/medical specifics not in the provided drafts/user message:
   - Do NOT invent statute numbers, deadlines, coverage limits, filing windows, or jurisdictional rules.
6) Remove all agent labels, meta commentary, and prompt scaffolding.
7) Make the article read like one coherent author wrote it.

ANTI-ECHO RULE:
- Use BLOG REQUIREMENTS as constraints, but DO NOT reproduce the BLOG REQUIREMENTS text verbatim in the output.

TASK:
Merge the section drafts into one cohesive blog with clean headings and transitions.
"""


# ----------------------------
# LLM + UTILS
# ----------------------------
def _make_llm(temperature: float, max_tokens: int) -> Together:
    api_key = os.getenv("TOGETHER_API_KEY") or os.getenv("TOGETHERAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing TOGETHER_API_KEY in environment.")
    return Together(
        model=COMPILER_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
    )


def _invoke_with_retries(llm: Together, messages: List[Any], attempts: int = 4) -> str:
    last_err: Optional[Exception] = None
    for i in range(attempts):
        try:
            out = llm.invoke(messages)
            if isinstance(out, str):
                return out
            if hasattr(out, "content"):
                return out.content or ""
            return str(out)
        except Exception as e:
            last_err = e
            time.sleep(0.5 + random.random() * 0.9)
            if DEBUGGING_MODE:
                print(f"[FullAgents] invoke attempt {i+1}/{attempts} failed: {e}")
    raise RuntimeError(f"Compiler invocation failed after {attempts} attempts: {last_err}")


_TAG_RE = re.compile(r"<<([A-Z0-9_]+)>>\n(.*?)(?=\n<<[A-Z0-9_]+>>\n|\Z)", re.S)


def _parse_tagged_prompt(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in _TAG_RE.findall(text or ""):
        out[k] = (v or "").strip()
    return out


def _strip_outer_quotes(t: str) -> str:
    t = (t or "").strip()
    if len(t) >= 2 and ((t[0] == '"' and t[-1] == '"') or (t[0] == "'" and t[-1] == "'")):
        return t[1:-1].strip()
    return t


def _strip_code_fences_and_meta(text: str) -> str:
    """
    Aggressive cleaning:
    - remove code fences
    - remove common meta prefixes + agent labels
    - remove variable assignment lines
    - unwrap quotes
    - remove echoed <<TAG>> blocks if they appear
    """
    if not text:
        return ""

    t = text.strip()

    # Remove code fences
    t = re.sub(r"```[\s\S]*?```", "", t).strip()

    # Remove common prefixes
    t = re.sub(r"^(assistant|response|output|answer)\s*:\s*", "", t, flags=re.I).strip()

    # Remove the common "ASSISTANT'S OUTPUT ..." scaffolding
    t = re.sub(r"^ASSISTANT[’']?S OUTPUT.*?:\s*", "", t, flags=re.I).strip()

    # Remove "Introduction Agent:" style leftovers if any
    t = re.sub(r"^\s*[A-Za-z0-9_ \-]{2,40}Agent\s*:\s*", "", t, flags=re.M).strip()

    # Remove assignment lines (COMPANY_X = ...)
    t = re.sub(r"^\s*[A-Z_]{3,}\s*=\s*.*$", "", t, flags=re.M).strip()

    # If the model echoed tagged blocks, remove them.
    # (We only want the blog output, not the prompt.)
    t = re.sub(r"<<[A-Z0-9_]+>>\n[\s\S]*?(?=\n<<[A-Z0-9_]+>>\n|\Z)", "", t).strip()

    # Unwrap outer quotes last
    t = _strip_outer_quotes(t)

    return t.strip()


def _looks_invalid(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if "```" in t:
        return True
    if t.startswith("{") or t.startswith("["):
        return True
    if t.lower().startswith(("assistant:", "ai:", "response:", "output:")):
        return True
    return False


def _build_compiler_input(tagged: Dict[str, str]) -> str:
    """
    Deterministic compiler input.
    IMPORTANT: include BLOG_REQUIREMENTS as constraints without asking to echo it.
    """
    blog_req = tagged.get("BLOG_REQUIREMENTS", "")
    user_msg = tagged.get("USER_MESSAGE", "")
    ctx = tagged.get("BUSINESS_CONTEXT", "")

    parts = [
        "BLOG REQUIREMENTS (CONSTRAINTS ONLY — DO NOT ECHO VERBATIM):",
        blog_req,
        "",
        "BLOG CONTEXT:",
        ctx,
        "",
        "USER MESSAGE:",
        user_msg,
        "",
        "SECTION DRAFTS (use these; do not invent facts):",
        "",
        "--- INTRO ---",
        tagged.get("DRAFT_INTRO", ""),
        "",
        "--- BODY / FAQs ---",
        tagged.get("DRAFT_BODY_FAQS", ""),
        "",
        "--- BUSINESS DESCRIPTION ---",
        tagged.get("DRAFT_BUSINESS_DESCRIPTION", ""),
        "",
        "--- SHORT CTA ---",
        tagged.get("DRAFT_SHORT_CTA", ""),
        "",
        "--- FINAL CTA ---",
        tagged.get("DRAFT_FINAL_CTA", ""),
        "",
        "--- REFERENCES ---",
        tagged.get("DRAFT_REFERENCES", ""),
    ]
    return "\n".join(parts).strip()


def _repair_output(llm: Together, compiler_in: str, bad_output: str) -> str:
    repair_sys = SYSTEM_DIRECTIVE_COMPILER + "\n\nReturn ONLY the blog in Markdown. No meta. Do not echo requirements."
    repair_user = (
        "Rewrite the full blog output correctly.\n\n"
        "COMPILER INPUT:\n"
        f"{compiler_in}\n\n"
        "BAD OUTPUT (do not keep bad formatting/meta/requirements echo):\n"
        f"{bad_output}"
    )
    raw = _invoke_with_retries(llm, [SystemMessage(content=repair_sys), HumanMessage(content=repair_user)], attempts=2)
    return _strip_code_fences_and_meta(raw)


def _validate_and_repair(llm: Together, raw: str, compiler_in: str) -> str:
    out = _strip_code_fences_and_meta(raw)

    if _looks_invalid(out):
        out = _repair_output(llm, compiler_in, out)

    # Final hard guard
    out = _strip_code_fences_and_meta(out)
    if not out.strip():
        out = "\n".join([
            "# Blog",
            "",
            "## Overview",
            "This article explains practical next steps and key considerations based on the information provided.",
            "",
            "## FAQs",
            "- See the guidance above for common questions and answers.",
            "",
            "## Next Steps",
            "If you need help, contact **{CALL_NUMBER}** or visit **{LINK}**.",
        ]).strip()

    return out.strip()


# ----------------------------
# PUBLIC FUNCTION
# ----------------------------
def Full_Blog_Writer(prompt: str, temperature: float) -> Tuple[str, str]:
    """
    Final compiler agent.
    Expects orchestrator to send a tagged prompt with:
      <<BLOG_REQUIREMENTS>>
      <<USER_MESSAGE>>
      <<BUSINESS_CONTEXT>>
      <<DRAFT_*>> blocks
    Returns: (used_prompt, compiled_markdown)
    """
    llm = _make_llm(temperature=temperature, max_tokens=FULL_TEXT_MAX_TOKENS)

    tagged = _parse_tagged_prompt(prompt)
    compiler_in = _build_compiler_input(tagged)

    if DEBUGGING_MODE:
        print(f"[FullAgents] compiler_in chars={len(compiler_in)}")
        # Do not print full compiler input (too large); print tag presence
        print("[FullAgents] tags present:",
              {k: (len(v) if isinstance(v, str) else 0) for k, v in tagged.items() if k in {
                  "BLOG_REQUIREMENTS","USER_MESSAGE","BUSINESS_CONTEXT",
                  "DRAFT_INTRO","DRAFT_BODY_FAQS","DRAFT_BUSINESS_DESCRIPTION",
                  "DRAFT_SHORT_CTA","DRAFT_FINAL_CTA","DRAFT_REFERENCES"
              }})

    messages = [
        SystemMessage(content=SYSTEM_DIRECTIVE_COMPILER),
        HumanMessage(content=compiler_in),
    ]
    raw = _invoke_with_retries(llm, messages, attempts=4)
    final = _validate_and_repair(llm, raw, compiler_in)
    return prompt, final

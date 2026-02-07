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
FULL_TEXT_MAX_TOKENS = 3584
FULL_TEXT_MIN_TOKENS = 1792
COMPILER_MODEL = "deepseek-ai/DeepSeek-V3"  # Fixed: Changed from FINAL_AGENT_MODEL to COMPILER_MODEL

# STRICT COMPILER DIRECTIVE
SYSTEM_DIRECTIVE_COMPILER = """You are the final compiler agent for a business blog article.

CRITICAL OUTPUT RULES:
1) Output MUST be plain Markdown ONLY (a single string).
2) Do NOT output JSON, code fences (```), HTML tags, XML, or templating syntax.
3) Do NOT include variable assignment lines (e.g., "COMPANY_NAME = ...").
4) Preserve placeholders exactly as-is (COMPANY_NAME, CALL_NUMBER, LINK, ADDRESS, STATE_NAME, etc.).
5) Do NOT add new legal/medical specifics not in the provided drafts/user message.
6) Remove all agent labels, meta commentary, and prompt scaffolding.
7) Make the article read like one coherent author wrote it.
TASK:
Merge the section drafts into one cohesive blog with clean headings and transitions.
"""

# LLM + UTILS
def _make_llm(temperature: float, max_tokens: int) -> Together:
    api_key = os.getenv("TOGETHER_API_KEY") or os.getenv("TOGETHERAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing TOGETHER_API_KEY in environment.")
    return Together(
        model=COMPILER_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key
    )

def _invoke_with_retries(llm: Together, messages: List[Any], attempts: int = 4) -> str:
    last_err: Optional[Exception] = None
    for i in range(attempts):
        try:
            if i > 0:  # Add delay between retries
                time.sleep(random.uniform(0.5, 2.0))
            
            response = llm.invoke(messages)
            content = response.content if hasattr(response, 'content') else str(response)
            
            if content and content.strip():
                return content
                
        except Exception as e:
            last_err = e
            if DEBUGGING_MODE:
                print(f"[FullAgents] Attempt {i+1} failed: {e}")
            continue
    
    raise RuntimeError(f"Compiler invocation failed after {attempts} attempts: {last_err}")
def _strip_outer_quotes(t: str) -> str:
    t = (t or "").strip()
    if len(t) >= 2 and ((t[0] == '"' and t[-1] == '"') or (t[0] == "'" and t[-1] == "'")):
        return t[1:-1].strip()
    return t
def _strip_code_fences_and_meta(text: str) -> str:
    """
    Aggressive cleaning
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

    t = re.sub(r"^\s*(system|human)\s*:\s*", "", t, flags=re.I | re.M).strip()

    # Unwrap outer quotes last
    t = _strip_outer_quotes(t)

    return t.strip()

# PUBLIC FUNCTION
def Full_Blog_Writer(prompt: str, temperature: float = 0.67) :
    """
    Final compiler agent.
    Returns: compiled_blog
    """
    print("[FullAgents] Full_Blog_Writer CALLED")

    llm = _make_llm(temperature=temperature, max_tokens=FULL_TEXT_MAX_TOKENS)

    if DEBUGGING_MODE:  print(f"[FullAgents] PROMPT TO COMPILER : {prompt}")
    
    messages = [SystemMessage(content=SYSTEM_DIRECTIVE_COMPILER), HumanMessage(content=prompt)]
    
    try:
        raw_response = _invoke_with_retries(llm, messages, attempts=4)
        cleaned_response = _strip_code_fences_and_meta(raw_response)
        
        if DEBUGGING_MODE:
            print(f"[FullAgents] Raw response length: {len(raw_response)}")
            print(f"[FullAgents] Cleaned response length: {len(cleaned_response)}")
        
        # Return both the prompt used and the compiled blog
        return cleaned_response
        
    except Exception as e:
        print(f"[FullAgents] Error in Full_Blog_Writer: {e}")
        # Return empty blog but keep the prompt for debugging
        return f"ERROR: {str(e)}"
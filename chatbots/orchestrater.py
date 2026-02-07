# chatbots/orchestrater.py
from __future__ import annotations
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Tuple, Any, List

from chatbots.SingularAgents import (
    Intro_Writing_Agent,
    Final_CTA_Agent,
    FAQs_Writing_Agent,
    Business_Description_Agent,
    Short_CTA_Agent,
    References_Writing_Agent
)
from chatbots.FullAgents import Full_Blog_Writer

# DEBUG PRINT HELPERS
def _log(msg: str) -> None:
    print(f"[Orchestrator] {msg}")
def _log_err(msg: str) -> None:
    print(f"[Orchestrator][ERROR] {msg}")


def _build_business_context(variables: Dict[str, str]) -> str:
    lines = []
    for k in [
        "USER_MESSAGE",
        "COMPANY_NAME",
        "CALL_NUMBER",
        "ADDRESS",
        "STATE_NAME",
        "LINK",
        "COMPANY_EMPLOYEE"
    ]:
        if k in variables and variables[k] is not None:
            lines.append(f"{k}: {variables[k]}")
    return "\n".join(lines).strip()


def _call_agent_with_timeout(agent_func, prompt: str, temperature: float, timeout: int = 30) -> str:
    """Helper to call an agent with timeout protection"""
    try:
        # Note: SingularAgents functions return (prompt, content) tuple
        used_prompt, content = agent_func(prompt, temperature)
        return content
    except Exception as e:
        _log_err(f"Agent {agent_func.__name__} failed: {e}")
        return f"ERROR in {agent_func.__name__}: {str(e)}"


# MAIN PIPELINE
def callAgents(
    user_message: str,
    COMPANY_NAME: str,
    CALL_NUMBER: str,
    ADDRESS: str,
    STATE_NAME: str,
    LINK: str,
    COMPANY_EMPLOYEE: str,
    PROMPT_FULLBLOG_FINAL: str,
    PROMPT_INTRO_FINAL: str,
    PROMPT_FINALCTA_FINAL: str,
    PROMPT_FULLFAQS_FINAL: str,
    PROMPT_BUSINESSDESC_FINAL: str,
    PROMPT_REFERENCES_FINAL: str,
    PROMPT_SHORTCTA_FINAL: str,
    TEMPERATURE: float = 0.73
) -> str:
    """
    variables: 
    - COMPANY_NAME
    - CALL_NUMBER
    - ADDRESS
    - STATE_NAME
    - LINK
    - COMPANY_EMPLOYEE
    - USER_MESSAGE
    prompts: 
    - PROMPT_FULLBLOG_FINAL
    - PROMPT_INTRO_FINAL
    - PROMPT_FINALCTA_FINAL
    - PROMPT_FULLFAQS_FINAL
    - PROMPT_BUSINESSDESC_FINAL
    - PROMPT_REFERENCES_FINAL
    - PROMPT_SHORTCTA_FINAL
    returns: Final blog only
    """
    t0 = time.time()
    _log("Starting blog generation pipeline...")
    
    # Create variables dictionary
    variables = {
        "USER_MESSAGE": user_message,
        "COMPANY_NAME": COMPANY_NAME,
        "CALL_NUMBER": CALL_NUMBER,
        "ADDRESS": ADDRESS,
        "STATE_NAME": STATE_NAME,
        "LINK": LINK,
        "COMPANY_EMPLOYEE": COMPANY_EMPLOYEE
    }
    
    _log("Received the following variables:")
    for k, v in variables.items():
        _log(f"  {k}: {v}")

    # 1) Run section agents in parallel
    _log("Launching 6 section agents in parallel...")
    
    agent_tasks = [
        (Intro_Writing_Agent, PROMPT_INTRO_FINAL),
        (Final_CTA_Agent, PROMPT_FINALCTA_FINAL),
        (FAQs_Writing_Agent, PROMPT_FULLFAQS_FINAL),
        (Business_Description_Agent, PROMPT_BUSINESSDESC_FINAL),
        (Short_CTA_Agent, PROMPT_SHORTCTA_FINAL),
        (References_Writing_Agent, PROMPT_REFERENCES_FINAL)
    ]
    
    agent_results = {}
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        # Submit all agent tasks
        future_to_agent = {}
        for agent_func, prompt in agent_tasks:
            future = executor.submit(_call_agent_with_timeout, agent_func, prompt, TEMPERATURE)
            future_to_agent[future] = agent_func.__name__
        
        # Collect results as they complete
        for future in as_completed(future_to_agent):
            agent_name = future_to_agent[future]
            try:
                result = future.result()
                agent_results[agent_name] = result
                _log(f"  {agent_name} completed successfully")
            except Exception as e:
                _log_err(f"  {agent_name} failed with exception: {e}")
                agent_results[agent_name] = f"ERROR: {str(e)}"

    _log("All section agents completed")

    # 2) Build compiler prompt 
    _log("Building final compiler prompt...")
    
    # Extract results in the specified order
    intro_content = agent_results.get('Intro_Writing_Agent', '')
    business_desc_content = agent_results.get('Business_Description_Agent', '')
    references_content = agent_results.get('References_Writing_Agent', '')
    short_cta_content = agent_results.get('Short_CTA_Agent', '')
    faqs_content = agent_results.get('FAQs_Writing_Agent', '')
    final_cta_content = agent_results.get('Final_CTA_Agent', '')
    
    # Build compiler prompt according to specifications
    compiler_prompt = (
        PROMPT_FULLBLOG_FINAL + 
        "\n\nRest of the generated parts of the blog:\n\n" + 
        "=== INTRODUCTION ===\n" + intro_content + "\n\n" +
        "=== BUSINESS DESCRIPTION ===\n" + business_desc_content + "\n\n" +
        "=== REFERENCES ===\n" + references_content + "\n\n" +
        "=== SHORT CTA ===\n" + short_cta_content + "\n\n" +
        "=== FAQS ===\n" + faqs_content + "\n\n" +
        "=== FINAL CTA ===\n" + final_cta_content
    )
    
    _log(f"Compiler prompt built | Length: {len(compiler_prompt)} characters")
    _log("==================================\n" + compiler_prompt + "\n...\n==================================")

    # 3) Call compiler agent
    _log("Calling final compiler agent...")
    final_blog = ""
    
    try:
        # Full_Blog_Writer returns (used_prompt, compiled_blog)
        used_prompt, compiled_blog = Full_Blog_Writer(compiler_prompt, TEMPERATURE)
        final_blog = compiled_blog.strip()
        _log("Final compiler agent completed successfully")
        _log(f"Output length: {len(final_blog)} characters")
        _log("First 500 chars of output:\n" + final_blog[:500] + "\n...")
    except Exception as e:
        _log_err(f"Compiler failed: {e}")
        _log_err(traceback.format_exc())
        final_blog = f"ERROR in final compilation: {str(e)}"

    dt = time.time() - t0
    _log(f"\n\nPipeline completed in {dt:.2f} seconds.")
    
    # RETURN ONLY FINAL BLOG 
    return final_blog
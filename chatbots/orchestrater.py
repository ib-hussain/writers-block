# orchestrater.py
from __future__ import annotations

import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Tuple, Any

from chatbots.SingularAgents import (
    Intro_Writing_Agent,
    Final_CTA_Agent,
    FAQs_Writing_Agent,
    Business_Description_Agent,
    Short_CTA_Agent,
    References_Writing_Agent,
)

from chatbots.FullAgents import Full_Blog_Writer


# =========================
# DEBUG PRINT HELPERS
# =========================
def _log(msg: str) -> None:
    print(f"[Orchestrator] {msg}")


def _log_err(msg: str) -> None:
    print(f"[Orchestrator][ERROR] {msg}")


# =========================
# PROMPT TAGGING
# =========================
def _tag_block(tag: str, content: str) -> str:
    content = (content or "").strip()
    return f"<<{tag}>>\n{content}\n"


def _build_business_context(variables: Dict[str, str]) -> str:
    lines = []
    for k in [
        "USER_MESSAGE",
        "COMPANY_NAME",
        "CALL_NUMBER",
        "ADDRESS",
        "STATE_NAME",
        "LINK",
        "COMPANY_EMPLOYEE",
        "COMPANY_EMPLOYEE_PRONOUN",
        "COMPANY_EMPLOYEE_POSITION",
    ]:
        if k in variables and variables[k] is not None:
            lines.append(f"{k}: {variables[k]}")
    return "\n".join(lines).strip()


def _build_compiler_prompt(
    blog_requirements: str,
    variables: Dict[str, str],
    drafts: Dict[str, str],
) -> str:
    """
    IMPORTANT:
    - Do NOT embed System/Human text here.
    - Only use tagged blocks so FullAgents can parse them.
    """
    business_context = _build_business_context(variables)

    prompt = ""
    prompt += _tag_block("BLOG_REQUIREMENTS", blog_requirements)
    prompt += _tag_block("USER_MESSAGE", variables.get("USER_MESSAGE", ""))
    prompt += _tag_block("BUSINESS_CONTEXT", business_context)

    prompt += _tag_block("DRAFT_INTRO", drafts.get("intro", ""))
    prompt += _tag_block("DRAFT_BODY_FAQS", drafts.get("faqs", ""))  # if you only have FAQs as "body", keep here
    prompt += _tag_block("DRAFT_BUSINESS_DESCRIPTION", drafts.get("business_description", ""))
    prompt += _tag_block("DRAFT_SHORT_CTA", drafts.get("short_cta", ""))
    prompt += _tag_block("DRAFT_FINAL_CTA", drafts.get("final_cta", ""))
    prompt += _tag_block("DRAFT_REFERENCES", drafts.get("integrate_references", ""))

    return prompt.strip()


# =========================
# SAFE AGENT RUNNER
# =========================
def _run_agent(agent_name: str, fn, prompt: str, temperature: float) -> Tuple[str, str]:
    """
    Returns (agent_name, output_text).
    Never raises to the executor.
    """
    try:
        _, out = fn(prompt, temperature)
        out = (out or "").strip()
        if not out:
            raise RuntimeError("empty output")
        return agent_name, out
    except Exception as e:
        _log_err(f"Agent '{agent_name}' failed: {e}")
        return agent_name, ""


# =========================
# MAIN PIPELINE
# =========================
def generate_blog_pipeline(
    variables: Dict[str, str],
    prompts: Dict[str, str],
    temperature: float,
) -> str:
    """
    variables: company info + USER_MESSAGE etc.
    prompts: dict containing the already-filled prompt strings:
        prompts["intro_prompt"], prompts["final_cta_prompt"], prompts["faqs_prompt"],
        prompts["business_description_prompt"], prompts["short_cta_prompt"], prompts["references_prompt"],
        prompts["full_blog_prompt"]   (THIS IS YOUR BLOG REQUIREMENTS STRING)
    returns: final blog markdown only
    """
    t0 = time.time()
    _log("Starting blog generation pipeline...")

    _log("Recieved the following variables:")
    for k, v in variables.items():
        _log(f"  {k}: {v}")

    # Extract requirements
    blog_requirements = (prompts.get("full_blog_prompt") or "").strip()
    if not blog_requirements:
        blog_requirements = "Write a clear SEO blog using the provided drafts."

    # 1) Run section agents in parallel
    _log("Launching 6 section agents in parallel...")

    agent_calls = [
        ("intro", Intro_Writing_Agent, prompts.get("intro_prompt", "")),
        ("final_cta", Final_CTA_Agent, prompts.get("final_cta_prompt", "")),
        ("faqs", FAQs_Writing_Agent, prompts.get("faqs_prompt", "")),
        ("business_description", Business_Description_Agent, prompts.get("business_description_prompt", "")),
        ("short_cta", Short_CTA_Agent, prompts.get("short_cta_prompt", "")),
        ("integrate_references", References_Writing_Agent, prompts.get("references_prompt", "")),
    ]

    drafts: Dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = []
        for name, fn, p in agent_calls:
            futures.append(ex.submit(_run_agent, name, fn, p, temperature))

        for fut in as_completed(futures):
            name, out = fut.result()
            drafts[name] = out
            if out:
                _log(f"Processing {name} agent result...")
                _log(f"{name} agent completed successfully | chars={len(out)}")
                _log(f"{name} agent completed successfully | Output: \n{drafts[name]}")
            else:
                _log_err(f"{name} agent returned empty output")

    # 2) Build compiler prompt (TAGGED)
    _log("Building final compiler prompt...")
    compiler_prompt = _build_compiler_prompt(
        blog_requirements=blog_requirements,
        variables=variables,
        drafts=drafts,
    )

    # IMPORTANT: Do NOT print compiler_prompt (it will leak in logs or UI copying)
    _log(f"Compiler prompt built | chars={len(compiler_prompt)}")
    _log(f"Compiler prompt: {compiler_prompt}")

    # 3) Call compiler agent
    _log("Calling final compiler agent...")
    try:
        _log("About to call Full_Blog_Writer() ...")
        _, final_blog = Full_Blog_Writer(compiler_prompt, temperature)
        final_blog = (final_blog or "").strip()
        _log("Final compiler agent completed | Output: \n" + final_blog)
    except Exception as e:
        _log_err(f"Compiler failed: {e}")
        _log_err(traceback.format_exc())
        # fallback: stitch drafts, but still don't leak prompt
        final_blog = "\n\n".join([
            drafts.get("intro", ""),
            drafts.get("faqs", ""),
            drafts.get("business_description", ""),
            drafts.get("short_cta", ""),
            drafts.get("final_cta", ""),
            drafts.get("integrate_references", ""),
        ]).strip()

    dt = time.time() - t0
    _log(f"Pipeline completed in {dt:.2f} seconds.")

    # RETURN ONLY FINAL BLOG (NO DEBUG / NO PROMPT / NO SYSTEM/HUMAN)
    return final_blog

# chatbots/orchestrater.py
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Tuple
import time

from chatbots.SingularAgents import (
    Intro_Writing_Agent,
    Final_CTA_Agent,
    FAQs_Writing_Agent,
    Business_Description_Agent,
    References_Writing_Agent,
    Short_CTA_Agent,
)
from chatbots.FullAgents import Full_Blog_Writer
from data.database_postgres import get_db

DEBUGGING_MODE = True
db = get_db()


class OrchestratorError(Exception):
    pass


def _now_ms() -> int:
    return int(time.time() * 1000)


def load_counter(filepath: str = "data/counter.txt") -> int:
    try:
        with open(filepath, "r") as f:
            return int(f.read().strip())
    except Exception:
        return 3


def write_counter(filepath: str = "data/counter.txt", COUNT: int = 5) -> None:
    with open(filepath, "w") as f:
        f.write(str(COUNT))


def write_profile_history(user_message: str, chatresponse: str):
    """
    IMPORTANT FIX:
    Store only the actual user_message in userprompt (not the giant used_prompt).
    This makes frontend history clean and prevents prompt leakage.
    """
    with db.conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO profileHistory (id, entry_date, entry, userprompt, chatresponse)
            VALUES (3, CURRENT_DATE, CURRENT_TIMESTAMP, %s, %s)
            """,
            (user_message, chatresponse),
        )
        conn.commit()


def write_progress():
    COUNTI = load_counter() + 1
    write_counter(COUNT=COUNTI)

    with db.conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO progress
              (id, entry_date, entry, writing, intro, final_cta, faqs,
               integrate_references, business_description, short_cta)
            VALUES
              (%s, CURRENT_DATE, CURRENT_TIMESTAMP, FALSE, FALSE, FALSE,
               FALSE, FALSE, FALSE, FALSE)
            ON CONFLICT (id) DO UPDATE SET
              entry_date = EXCLUDED.entry_date,
              entry = EXCLUDED.entry,
              writing = FALSE,
              intro = FALSE,
              final_cta = FALSE,
              faqs = FALSE,
              integrate_references = FALSE,
              business_description = FALSE,
              short_cta = FALSE
            """,
            (COUNTI,),
        )
        conn.commit()


def mark_progress(column_name: str):
    COUNTI = load_counter()
    with db.conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            UPDATE progress
            SET {column_name} = TRUE
            WHERE id = %s
            """,
            (COUNTI,),
        )
        conn.commit()


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
    TEMPERATURE: float = 0.70,
) -> str:
    """
    Main orchestrator:
    - Runs section agents in parallel
    - Calls compiler agent once
    - Returns ONLY the final compiled blog (no debug scaffolding)
    """
    t0 = _now_ms()

    print("\n[Orchestrator] ==================================================")
    print("[Orchestrator] Starting pipeline")
    print(f"[Orchestrator] TEMPERATURE={TEMPERATURE}")
    print("[Orchestrator] Business vars received:")
    print(f"  COMPANY_NAME: {COMPANY_NAME}")
    print(f"  CALL_NUMBER: {CALL_NUMBER}")
    print(f"  ADDRESS: {ADDRESS}")
    print(f"  STATE_NAME: {STATE_NAME}")
    print(f"  LINK: {LINK}")
    print(f"  COMPANY_EMPLOYEE: {COMPANY_EMPLOYEE}")
    print(f"  USER_MESSAGE: {user_message}")
    print("[Orchestrator] ==================================================\n")

    try:
        write_progress()
    except Exception as e:
        print(f"[Orchestrator] Progress init failed (non-fatal): {e}")

    business_context = (
        f"COMPANY_NAME: {COMPANY_NAME}\n"
        f"CALL_NUMBER: {CALL_NUMBER}\n"
        f"ADDRESS: {ADDRESS}\n"
        f"STATE_NAME: {STATE_NAME}\n"
        f"LINK: {LINK}\n"
        f"COMPANY_EMPLOYEE: {COMPANY_EMPLOYEE}\n"
    )

    # Build agent prompts (focused, no giant assignment dumps)
    intro_prompt = f"{PROMPT_INTRO_FINAL}\n\nUser message:\n{user_message}\n\nBusiness context:\n{business_context}"
    finalcta_prompt = f"{PROMPT_FINALCTA_FINAL}\n\nUser message:\n{user_message}\n\nBusiness context:\n{business_context}"
    faqs_prompt = f"{PROMPT_FULLFAQS_FINAL}\n\nUser message:\n{user_message}\n\nBusiness context:\n{business_context}"
    bizdesc_prompt = f"{PROMPT_BUSINESSDESC_FINAL}\n\nUser message:\n{user_message}\n\nBusiness context:\n{business_context}"
    refs_prompt = f"{PROMPT_REFERENCES_FINAL}\n\nUser message:\n{user_message}\n\nBusiness context:\n{business_context}"
    shortcta_prompt = f"{PROMPT_SHORTCTA_FINAL}\n\nUser message:\n{user_message}\n\nBusiness context:\n{business_context}"

    agent_jobs = {
        "intro": (Intro_Writing_Agent, intro_prompt, "intro"),
        "final_cta": (Final_CTA_Agent, finalcta_prompt, "final_cta"),
        "faqs": (FAQs_Writing_Agent, faqs_prompt, "faqs"),
        "business_description": (Business_Description_Agent, bizdesc_prompt, "business_description"),
        "integrate_references": (References_Writing_Agent, refs_prompt, "integrate_references"),
        "short_cta": (Short_CTA_Agent, shortcta_prompt, "short_cta"),
    }

    agent_results: Dict[str, str] = {k: "" for k in agent_jobs.keys()}

    print("[Orchestrator] Launching 6 section agents in parallel...")
    t_agents0 = _now_ms()

    with ThreadPoolExecutor(max_workers=6) as executor:
        future_map = {
            executor.submit(fn, prmpt, TEMPERATURE): (key, progress_col)
            for key, (fn, prmpt, progress_col) in agent_jobs.items()
        }

        for future in as_completed(future_map):
            key, progress_col = future_map[future]
            t_one0 = _now_ms()
            try:
                _, output = future.result()
                out = (output or "").strip()
                agent_results[key] = out

                try:
                    mark_progress(progress_col)
                except Exception as e:
                    print(f"[Orchestrator] mark_progress({progress_col}) failed (non-fatal): {e}")

                dt = _now_ms() - t_one0
                print(f"[Orchestrator] ✅ {key} done in {dt}ms | chars={len(out)}")

            except Exception as e:
                agent_results[key] = ""
                dt = _now_ms() - t_one0
                print(f"[Orchestrator] ❌ {key} failed in {dt}ms | err={e}")

    print(f"[Orchestrator] Section agents finished in {_now_ms() - t_agents0}ms")

    # ------------------------------------------------------------
    # CRITICAL FIX:
    # Do NOT prefix the compiler prompt with PROMPT_FULLBLOG_FINAL.
    # Instead pass it as a tagged block so it doesn't get echoed.
    # ------------------------------------------------------------
    print("[Orchestrator] Building tagged compiler prompt...")
    compiler_prompt = (
        f"<<BLOG_REQUIREMENTS>>\n{PROMPT_FULLBLOG_FINAL}\n\n"
        f"<<USER_MESSAGE>>\n{user_message}\n\n"
        f"<<BUSINESS_CONTEXT>>\n{business_context}\n"
        f"<<DRAFT_INTRO>>\n{agent_results.get('intro', '')}\n\n"
        f"<<DRAFT_BODY_FAQS>>\n{agent_results.get('faqs', '')}\n\n"
        f"<<DRAFT_BUSINESS_DESCRIPTION>>\n{agent_results.get('business_description', '')}\n\n"
        f"<<DRAFT_SHORT_CTA>>\n{agent_results.get('short_cta', '')}\n\n"
        f"<<DRAFT_FINAL_CTA>>\n{agent_results.get('final_cta', '')}\n\n"
        f"<<DRAFT_REFERENCES>>\n{agent_results.get('integrate_references', '')}\n"
    )

    print("[Orchestrator] Calling final compiler agent...")
    t_comp0 = _now_ms()
    try:
        _, final_output = Full_Blog_Writer(compiler_prompt, TEMPERATURE)

        if not final_output or not final_output.strip():
            raise OrchestratorError("Compiler returned empty output")

        dt_comp = _now_ms() - t_comp0
        print(f"[Orchestrator] ✅ Compiler done in {dt_comp}ms | chars={len(final_output)}")

        # Persist final result (store only user_message as userprompt)
        try:
            write_profile_history(user_message, final_output)
        except Exception as e:
            print(f"[Orchestrator] write_profile_history failed (non-fatal): {e}")

        try:
            mark_progress("writing")
        except Exception as e:
            print(f"[Orchestrator] mark_progress(writing) failed (non-fatal): {e}")

        total_ms = _now_ms() - t0
        print(f"[Orchestrator] Pipeline completed in {total_ms}ms")
        print("[Orchestrator] Returning FINAL BLOG ONLY (no debug scaffolding)\n")
        return final_output.strip()

    except Exception as e:
        print(f"[Orchestrator] ❌ Final compiler failed: {e}")
        raise OrchestratorError(f"Final compiler failed: {e}")

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Tuple
from datetime import datetime
import time

from chatbots.SingularAgents import (Intro_Writing_Agent, Final_CTA_Agent, 
                           FAQs_Writing_Agent, Business_Description_Agent, 
                           References_Writing_Agent, Short_CTA_Agent)
from chatbots.FullAgents import Full_Blog_Writer
from data.database_postgres import get_db 
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
db = get_db()

class OrchestratorError(Exception):
    pass
def write_profile_history(userprompt: str, chatresponse: str):
        with db.conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO profileHistory (id, entry_date, entry, "Userprompt", "chatResponse")
                VALUES (3, CURRENT_DATE, CURRENT_TIMESTAMP, %s, %s)
                """,
                (userprompt, chatresponse)
            )
            conn.commit()
def write_progress():
        with db.conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO progress (id, entry_date,entry, writing, intro, final_cta, faqs, integrate_references, business_description, short_cta)
                VALUES (3, CURRENT_DATE, CURRENT_TIMESTAMP, FALSE,   FALSE, FALSE,    FALSE, FALSE,               FALSE,                FALSE)
                """
            )
            conn.commit()
def mark_progress(column_name: str):
        with db.conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                UPDATE progress
                SET {column_name} = TRUE
                WHERE entry_date = CURRENT_DATE
                """
            )
            conn.commit()
def callAgents(
    user_message:str ,
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
    TEMPERATURE: float = 0.7
    ) -> str:
    
    write_progress()
    start = time.time()
    agent_map = {
        "intro": (Intro_Writing_Agent, PROMPT_INTRO_FINAL),
        "final_cta": (Final_CTA_Agent, PROMPT_FINALCTA_FINAL),
        "faqs": (FAQs_Writing_Agent, PROMPT_FULLFAQS_FINAL),
        "business_description": (Business_Description_Agent, PROMPT_BUSINESSDESC_FINAL),
        "short_cta": (Short_CTA_Agent, PROMPT_SHORTCTA_FINAL),
        "integrate_references": (References_Writing_Agent, PROMPT_REFERENCES_FINAL)
    }
    agent_results = {}
    # ---- Parallel execution ----
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(fn, prompt, TEMPERATURE): progress_col
            for progress_col, (fn, prompt) in agent_map.items()
        }
        for future in as_completed(futures):
            progress_col = futures[future]
            try:
                used_prompt, output = future.result(timeout=90)
                # Persist immediately
                write_profile_history(used_prompt, output)
                mark_progress(progress_col)
                agent_results[progress_col] = output
            except Exception as e:
                raise OrchestratorError(f"Agent failed ({progress_col}): {e}")
    # ---- Final writer (sequential) ----
    # issue: fix this bullshit
    full_prompt = PROMPT_FULLBLOG_FINAL.format(
        INTRO=agent_results["intro"],
        FINAL_CTA=agent_results["final_cta"],
        FAQ=agent_results["faqs"],
        Buisness_DESCRIPTION=agent_results["business_description"],
        SHORT_CTA=agent_results["short_cta"],
        REFERENCES=agent_results["integrate_references"],
        COMPANY_NAME=COMPANY_NAME,
        CALL_NUMBER=CALL_NUMBER,
        ADDRESS=ADDRESS,
        STATE_NAME=STATE_NAME,
        LINK=LINK,
        COMPANY_EMPLOYEE=COMPANY_EMPLOYEE,
        FullBlog =PROMPT_FULLBLOG_FINAL,
        USER_MESSAGE=user_message
    )
    final_output = Full_Blog_Writer(full_prompt, TEMPERATURE)

    write_profile_history(full_prompt, final_output)
    mark_progress("writing")

    duration = round(time.time() - start, 2)
    print(f"[Orchestrator] Completed in {duration} seconds.")
    return final_output

# orchestrater.py
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
def load_counter(filepath: str = "data/counter.txt") -> int:
    """
    Read an integer from a file and return it.
    If file doesn't exist or contains invalid data, return default value of 3.
    """
    try:
        with open(filepath, 'r') as f:
            content = f.read().strip()
            return int(content)
    except (FileNotFoundError, ValueError, IOError):
        # If file doesn't exist or contains invalid data, return default
        return 3
def write_counter(filepath: str = "data/counter.txt", COUNT: int=5 ) -> None:
    """
    Write an integer to a file.
    """
    with open(filepath, 'w') as f:
        f.write(str(COUNT))
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
    COUNTI = load_counter()
    COUNTI+=1
    write_counter(COUNT=COUNTI)
    with db.conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO progress (id, entry_date,entry, writing, intro, final_cta, faqs, integrate_references, business_description, short_cta)
                VALUES (%s, CURRENT_DATE, CURRENT_TIMESTAMP, FALSE,   FALSE, FALSE,    FALSE, FALSE,               FALSE,                FALSE)
                """,
                (COUNTI)
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
                WHERE id = {COUNTI}
                """
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
    TEMPERATURE: float = 0.70
) -> str:

    # Keep your existing progress init, but don't crash if it's not in scope
    try:
        write_progress()
    except Exception:
        pass

    start = time.time()

    # Common block appended to every section prompt (includes user_message — critical)
    common_vars = (
        "USER_MESSAGE = " + user_message + "\n"
        "COMPANY_NAME = " + COMPANY_NAME + "\n"
        "CALL_NUMBER = " + CALL_NUMBER + "\n"
        "ADDRESS = " + ADDRESS + "\n"
        "STATE_NAME = " + STATE_NAME + "\n"
        "LINK = " + LINK + "\n"
        "COMPANY_EMPLOYEE = " + COMPANY_EMPLOYEE + "\n"
    )
    agent_map = {
        "intro": (Intro_Writing_Agent, PROMPT_INTRO_FINAL + "\n" + common_vars),
        "final_cta": (Final_CTA_Agent, PROMPT_FINALCTA_FINAL + "\n" + common_vars),
        "faqs": (FAQs_Writing_Agent, PROMPT_FULLFAQS_FINAL + "\n" + common_vars),
        "business_description": (Business_Description_Agent, PROMPT_BUSINESSDESC_FINAL + "\n" + common_vars),
        "short_cta": (Short_CTA_Agent, PROMPT_SHORTCTA_FINAL + "\n" + common_vars),
        "integrate_references": (References_Writing_Agent, PROMPT_REFERENCES_FINAL + "\n" + common_vars),
    }

    agent_results = {}

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(fn, prompt, TEMPERATURE): progress_col
            for progress_col, (fn, prompt) in agent_map.items()
        }

        for future in as_completed(futures):
            progress_col = futures[future]
            try:
                used_prompt, output = future.result(timeout=90)

                # Persist immediately (your desired behaviour)
                write_profile_history(used_prompt, output)
                mark_progress(progress_col)

                agent_results[progress_col] = output

            except Exception as e:
                raise OrchestratorError(f"Agent failed ({progress_col}): {e}")

    full_prompt = (
        PROMPT_FULLBLOG_FINAL + "\n"
        "The following is the user prompt:\n" + user_message + "\n\n"
        "The following are the results of the previous agents:\n\n"
        "Introduction Agent:\n" + agent_results["intro"] + "\n\n"
        "Final CTA Agent:\n" + agent_results["final_cta"] + "\n\n"
        "FAQs Agent:\n" + agent_results["faqs"] + "\n\n"
        "Business Description Agent:\n" + agent_results["business_description"] + "\n\n"
        "Short CTA Agent:\n" + agent_results["short_cta"] + "\n\n"
        "Integrate References Agent:\n" + agent_results["integrate_references"] + "\n\n"
        + common_vars
    )

    used_prompt, final_output = Full_Blog_Writer(full_prompt, TEMPERATURE)

    write_profile_history(used_prompt, final_output)
    mark_progress("writing")

    duration = round(time.time() - start, 2)
    print(f"[Orchestrator] Completed in {duration} seconds.")

    return final_output
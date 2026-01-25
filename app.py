# app.py
from __future__ import annotations
import os
from datetime import datetime, date
from typing import Tuple
from flask import Flask, jsonify, request, redirect
from psycopg2 import sql
import psycopg2
import psycopg2.extras
from psycopg2.pool import PoolError

from data.database_postgres import get_db
#==================================================================================================================================================
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
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass
SECRET_KEY = os.getenv("SECRET_KEY")
#==================================================================================================================================================
# FLASK
app = Flask(
    "Writer's Block",
    static_folder="web_files",
    static_url_path="/web_files"
)
app.secret_key = SECRET_KEY
# DB POOL
db = get_db()
# HELPERS
def json_error(code: str, message: str, http_status: int = 500, **extra):
    payload = {"success": False, "code": code, "message": message}
    if extra:
        payload.update(extra)
    return jsonify(payload), http_status
def clamp_int(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))
def parse_yyyy_mm_dd(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()
def get_profilehistory_columns(conn) -> Tuple[str, str]:
    """
    Detect actual column names in profilehistory table.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name='profilehistory'
            ORDER BY ordinal_position;
        """)
        cols = [r["column_name"] for r in cur.fetchall()]
        colset = set(cols)

        if "Userprompt" in colset and "chatResponse" in colset:
            return '"Userprompt"', '"chatResponse"'

        if "userprompt" in colset and "chatresponse" in colset:
            return "userprompt", "chatresponse"

        raise RuntimeError(
            f"profileHistory columns not found. Present columns: {cols}. "
            f"Expected either (Userprompt, chatResponse) or (userprompt, chatresponse)."
        )
# BASIC PAGES
@app.route("/")
def index():
    return redirect("/web_files/chatbot.html")
# API: TABLES
@app.route("/api/db/table/<table_name>")
def api_db_table(table_name: str):
    """
    Return a single table (safe identifier handling) with FULL rows.
    """
    excluded = {"profilehistory"}
    try:
        req = (table_name or "").strip()
        if not req:
            return json_error("MISSING_TABLE", "Missing table_name in URL path.", 400)
        with db.conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT tablename
                    FROM pg_catalog.pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY tablename ASC;
                """)
                allowed = [r["tablename"] for r in cur.fetchall()]
                allowed_lc = {t.lower(): t for t in allowed}
                if req.lower() in excluded:
                    return json_error("TABLE_EXCLUDED", "This table is excluded from DB views.", 403, table=req)
                actual_name = allowed_lc.get(req.lower())
                if not actual_name:
                    return json_error("UNKNOWN_TABLE", "Table not found.", 404, table=req, available=allowed)
                
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema='public' AND table_name=%s
                    ORDER BY ordinal_position;
                """, (actual_name,))
                columns = [r["column_name"] for r in cur.fetchall()]
                
                tbl_ident = sql.Identifier(actual_name)
                cur.execute(sql.SQL("SELECT * FROM {}").format(tbl_ident))
                rows = cur.fetchall()
        
        return jsonify({
            "success": True,
            "table": {
                "name": actual_name,
                "columns": columns,
                "row_count": len(rows),
                "rows": rows
            }
        }), 200
    except PoolError as e:
        return json_error("POOL_EXHAUSTED", "DB connection pool exhausted.", 500, details=str(e))
    except Exception as e:
        return json_error("DB_TABLE_FAIL", "Failed to load table.", 500, details=str(e))
# API: TOKENS (WORDS) PER DAY FOR CURRENT MONTH STATS
@app.route("/api/stats/tokens/month")
def api_tokens_month():
    try:
        with db.conn() as conn:
            user_col, resp_col = get_profilehistory_columns(conn)

            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                sql_query = f"""
                    WITH daily AS (
                        SELECT
                            entry_date,
                            COALESCE(
                                SUM(
                                    CASE
                                      WHEN {user_col} IS NULL OR btrim({user_col}) = '' THEN 0
                                      ELSE array_length(regexp_split_to_array(btrim({user_col}), '\\s+'), 1)
                                    END
                                ), 0
                            ) AS input_words,
                            COALESCE(
                                SUM(
                                    CASE
                                      WHEN {resp_col} IS NULL OR btrim({resp_col}) = '' THEN 0
                                      ELSE array_length(regexp_split_to_array(btrim({resp_col}), '\\s+'), 1)
                                    END
                                ), 0
                            ) AS output_words
                        FROM profileHistory
                        WHERE entry_date >= date_trunc('month', CURRENT_DATE)::date
                          AND entry_date < (date_trunc('month', CURRENT_DATE) + interval '1 month')::date
                        GROUP BY entry_date
                    )
                    SELECT
                        to_char(entry_date, 'DD') AS day,
                        input_words,
                        output_words
                    FROM daily
                    ORDER BY entry_date ASC;
                """
                cur.execute(sql_query)
                daily = cur.fetchall()

                cur.execute("SELECT to_char(CURRENT_DATE, 'Mon YYYY') AS month_label;")
                month_label = cur.fetchone()["month_label"]

        return jsonify({"success": True, "month_label": month_label, "daily": daily}), 200

    except PoolError as e:
        return json_error("POOL_EXHAUSTED", "DB pool exhausted.", 500, details=str(e))
    except Exception as e:
        return json_error("TOKENS_MONTH_FAIL", "Failed to compute token stats.", 500, details=str(e))
# API: PROFILE HISTORY BY DATE
@app.route("/api/profile/history")
def api_profile_history_by_date():
    d = (request.args.get("date") or "").strip()
    if not d:
        return json_error("MISSING_DATE", "Missing date parameter. Use ?date=YYYY-MM-DD", 400)

    try:
        parsed_date = parse_yyyy_mm_dd(d)
    except ValueError:
        return json_error("BAD_DATE_FORMAT", "Invalid date format. Use YYYY-MM-DD", 400, received=d)

    try:
        with db.conn() as conn:
            user_col, resp_col = get_profilehistory_columns(conn)

            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                sql_query = f"""
                    SELECT
                        id,
                        entry AS entry,
                        entry_date AS entry_date,
                        {user_col} AS userprompt,
                        {resp_col} AS chatresponse
                    FROM profileHistory
                    WHERE entry_date = %s
                    ORDER BY id ASC;
                """
                cur.execute(sql_query, (parsed_date,))
                rows = cur.fetchall()
                
                if not rows:
                    try:
                        cur.execute("""
                            SELECT
                              COUNT(*) AS total_rows,
                              COUNT(*) FILTER (WHERE (entry AT TIME ZONE 'UTC')::date = %s) AS utc_match,
                              COUNT(*) FILTER (WHERE (entry AT TIME ZONE 'Asia/Karachi')::date = %s) AS pk_match
                            FROM profileHistory;
                        """, (parsed_date, parsed_date))
                        diag = cur.fetchone() or {}
                    except Exception as e:
                        diag = {"diag_error": str(e)}
                    
                    return jsonify({
                        "success": False,
                        "code": "NO_ROWS_FOR_DATE",
                        "message": "No profileHistory rows found for the given entry_date.",
                        "requested_date": d,
                        "diagnostics": diag,
                        "hint": (
                            "If utc_match > 0 or pk_match > 0, your data exists but entry_date "
                            "does not match the selected date due to timezone/date derivation."
                        )
                    }), 404
        
        return jsonify({"success": True, "code": "OK", "date": d, "rows": rows}), 200
    except PoolError as e:
        return json_error("POOL_EXHAUSTED", "DB pool exhausted.", 500, details=str(e))
    except Exception as e:
        return json_error("PROFILE_HISTORY_FAIL", "Failed to load profile history.", 500, details=str(e))
# API: CHAT ENDPOINT
@app.route('/api/chat', methods=['POST'])
def handle_chat():
    """
    Handle chatbot messages.
    Stores user prompt and generated response in profileHistory.
    """
    try:
        # issue: change this so that the variables here are filled with there default values on the frontend and also accessible for the user to edit, 
        # and the ones without any default value will be filled after being retrieved from the frontend
        # USER INPUTS 
        ### PROMPT VARIABLES (defaults - will be overridden by UI)
        TITLE=""
        KEYWORDS="lawyer, attorney, consultation, claim, accident, case, insurance, insurance company, evidence, police report, medical records, witness statements, compensation, damages, liability, settlement, legal process, statute limitations, comparative negligence, policy limits, contingency fee, trial, litigation, negotiation, expert witnesses, accident reconstruction, dashcam footage, surveillance footage, medical bills, total loss, gap"
        INSERT_INTRO_QUESTION=""
        INSERT_FAQ_QUESTIONS=""
        SOURCE=""
        COMPANY_NAME=""
        CALL_NUMBER=""
        ADDRESS=""  
        STATE_NAME=""
        LINK=""
        COMPANY_EMPLOYEE=""
        BLOGFOREXAMPLE=""
        # issue:
        #  Retrival method: 
        # There is a table in the database for this: blogdata
        # Columns:  blogID, blogText 
        BLOGPART_INTRO=""
        BLOGPART_FINALCTA=""
        BLOGPART_FAQS=""
        BLOGPART_BUSINESSDESC=""
        BLOGPART_SHORTCTA=""
        # issue: once the numbers are retrieved, retrieve the appropriate examples from the database and combines them inside the above variables in the 
        #        form of 
        #        Example 1:
        #        //        {example text}
        #        Example 2:
        #        //        {example text}
        #  Retrival method: 
        # There is a table in the database for this: blogparts
        # Columns:  blogID,intro, final_cta, FAQs, business_description, integrate_references, short_cta
        TEMPERATURE="0.70"
        BLOGTYPE="Legal"
        PROMPT_FULLBLOG=f""" We are writing a clear, SEO-optimised article titled “{TITLE}”. This article must directly answer each header in the very first sentence of each relevant section. Then, it should go into specific, well-researched, and helpful details.
        You MUST use all of the following keywords naturally throughout the article:
        “{KEYWORDS}”
        * Use these keywords even when paraphrasing.
        * Do not skip any keyword throughout the entire article.
        * Use an active voice, and avoid passive voice unless absolutely necessary.
        * Always keep sentences short or split them when needed.
        * Use strong transitions.
        * Support points with real-world facts, examples, or data.
        * Each paragraph must begin with a direct, clear answer.
        * The tone should be informative, direct, and easy to follow.
        I have given the headers (outline sections). You will expand them with strong content, following these rules for the entire article.
        This should be the example format: {BLOGFOREXAMPLE}"""
        PROMPT_INTRO=f"""Write intro answering the question: {INSERT_INTRO_QUESTION}. Provide two paragraphs, each 60 words. The first paragraph must give a direct and relevant answer to the question, using short, active sentences, smooth transitions, and easy-to-follow language. The second paragraph must be a strong call to action, connected naturally to the topic. Write in the second person. Keep every sentence under 15 words for readability. Use a Flesch Reading Score–friendly style.
        This should be the format: {BLOGPART_INTRO}"""
        PROMPT_FINALCTA=f"""Write a two-paragraph call to action. Each paragraph must have 70 words. The first paragraph should explain the problems the reader faces based on the topic. The second paragraph should explain how we can help resolve those problems. In the second paragraph, you must use the name, phone number, and location given in the reference. Write in the second person, keep every sentence under 15 words, and use transition words for smooth flow. Keep the tone clear, active, and easy to follow for a high Flesch Reading Score.
        This should be the format: {BLOGPART_FINALCTA}"""
        PROMPT_FULLFAQS=f"""Answer the following FAQs clearly and directly, using the following formatting and content rules:
        {INSERT_FAQ_QUESTIONS}
        Each question should be formatted as an H4 with bold text and Title Case.
        Seamlessly integrate the following keywords wherever relevant and natural: {KEYWORDS}

        * Answer length should be between 60 to 70 words.
        * Begin with a direct answer (e.g., “Yes,” or “No,” if applicable), followed by a clear explanation.
        * Use an active voice throughout.
        * Use strong transitions between ideas and connect sentences smoothly.
        * If a sentence becomes long, break it using a short, clear transition or supporting sentence.
        * Do not include fluff or filler. Every sentence must add value and connect logically.
        * Make the tone informative and easy to follow without oversimplifying medical or legal terms.
        * Avoid sudden info dumps; flow should be natural and progressive.
        * Make sure no sentence or idea feels out of place or rushed.
        * Use real medical and legal insight where needed, and avoid vague or generic statements.
        * Do not overuse any keyword or repeat the same idea unnecessarily.
        * All the sentences should only answer the question, no other irrelevant info.
        This should be the format: {BLOGPART_FAQS}"""
        PROMPT_BUSINESSDESC=f""" Write a business description based on the title: {TITLE}. Start with a direct 70-word opening paragraph that answers the question clearly. Then, include six bullet points in the middle, each 15 words long, highlighting symptoms, risks, steps, legal options or key details connected to the topic. After the bullets, write a closing 70-word paragraph explaining how we can help. Use second person, active voice, and short sentences under 15 words. Add smooth transitions for flow and ensure a high Flesch Reading Score.
        This is an example: {BLOGPART_BUSINESSDESC}"""
        PROMPT_REFERENCES=f""" When integrating references, only use credible, trustworthy sources such as government sites, universities, medical journals, legal journals, or recognized organizations. Do not use competitors or promotional sources. Introduce the reference naturally with phrases like ‘According to {SOURCE}’ or ‘A study by {SOURCE} found…’. Keep sentences short, active, and easy to follow. Use references to support key points, not overwhelm the reader. Include at least 3–4 references throughout the blog, but use more if needed for accuracy. At the end, provide the full source in a consistent format.
        This should be the format:
            For Legal Blogs:
                1. According to NIH research, anxiety and traumatic stress symptoms are common after a car crash. In a study of 62 hospitalized patients, 55% reported moderate to severe anxiety.
                2. For instance, a case study on NCBI revealed that a 27-year-old woman developed severe neurological problems after a side-impact car accident. Despite regular CT scans, an MRI later showed severe C1/C2 joint damage.
            For Health Blogs:
                1. According to NIH, vibration therapy (VT) improves neuromuscular performance by increasing strength, power, and kinesthetic awareness. According to PubMed, smoking increases the risk of cartilage loss. By avoiding smoking, you protect your cartilage, allowing tissues to heal better and respond more effectively to exercises.For instance, a case study on NCBI revealed that a 27-year-old woman developed severe neurological problems after a side-impact car accident. Despite regular CT scans, an MRI later showed severe C1/C2 joint damage.
                2. According to the NIH, a review of 26 studies showed that past lower extremity injuries raise the risk of reinjury. These studies showed that previous anterior cruciate ligament tears often lead to repeated ACL injuries or other leg problems. Moreover, hamstring strains increase the chance of another hamstring injury. According to PubMed, cryotherapy (ice therapy)may help reduce severe knee pain in patients with knee osteoarthritis. A systematic review of five RCTs found a significant decrease in knee pain. According to BMC, 141 out of 215 patients participated in a second opinion for knee arthroplasty. During this program, knee surgeons reassessed diagnoses and recommended surgery for 40% of patients after checking them in person. After the second opinion, 41% of patients chose surgery, 25% decided against it, and 25% remained unsure.
                """
        PROMPT_SHORTCTA=f"""Write a short 2–3 line call to action that directly connects to the problems discussed in the section. Emphasize how our doctors or lawyers can help the reader manage those challenges. Keep sentences short, active, and easy to follow. Avoid using our name, phone number, or location. Only use phrases like contact us or reach out to us naturally within the text.
        This should be the format: {BLOGPART_SHORTCTA}"""
        # issue: i just want all the variables to be edited by the user and also contain the retrieved text from the above variables before being sent as a prompt to the LLM


        # --- Build prompt with variables ---
        VAR_ORDER = []

        # issue: Replace this with actual imported function from 
        # chatbots.callAgents(PROMPT_FULLBLOG,PROMPT_INTRO,PROMPT_FINALCTA,PROMPT_FULLFAQS,PROMPT_BUSINESSDESC,PROMPT_REFERENCES, PROMPT_SHORTCTA,TEMPERATURE ) 
        # with LLM API call, for now, using echo response
        bot_response = f"Echo: Nothing"

        # --- Persist to DB ---
        # with db.conn() as conn:
        #     with conn.cursor() as cur:
        #         insert_sql = f"""
        #             INSERT INTO profileHistory (id,entry_date, entry, userprompt, chatresponse)
        #             VALUES (3,CURRENT_DATE, CURRENT_TIMESTAMP, %s, %s);
        #         """
        #         cur.execute(insert_sql, (composed_user_prompt, bot_response))
        #         conn.commit()
        # issue: this need not be here but in the chatbot.py file due to the fact that each agent will send its own prompt and bot response

        return jsonify({
            "success": True,
            "response": bot_response,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except PoolError as e:
        return json_error("POOL_EXHAUSTED", "Database connection pool exhausted", 500, details=str(e))
    except psycopg2.Error as e:
        app.logger.error(f"Database error in chat endpoint: {e}")
        return json_error("DB_ERROR", "Database operation failed", 500, details=str(e))
    except Exception as e:
        app.logger.error(f"Chat endpoint error: {e}")
        return json_error("CHAT_FAILED", "Failed to process chat message", 500, details=str(e))

# MAIN (local dev)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=DEBUGGING_MODE)
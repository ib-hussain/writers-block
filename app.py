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

from chatbots.orchestrater import callAgents
from data.database_postgres import get_db, json_error, parse_yyyy_mm_dd, get_profilehistory_columns
#==================================================================================================================================================
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
    Retrieves variables from frontend, fetches blog examples from database,
    and prepares prompts for LLM.
    """
    try:
        data = request.get_json(silent=True) or {}
        user_message = (data.get("message") or "").strip()
        vars_payload = data.get("vars") or {}
        if not user_message: return json_error("EMPTY_MESSAGE", "Message cannot be empty", 400)

        # Extract all variables from frontend
        TITLE = vars_payload.get("TITLE", "").strip()
        KEYWORDS = vars_payload.get("KEYWORDS", "").strip()
        INSERT_INTRO_QUESTION = vars_payload.get("INSERT_INTRO_QUESTION", "").strip()
        INSERT_FAQ_QUESTIONS = vars_payload.get("INSERT_FAQ_QUESTIONS", "").strip()
        SOURCE = vars_payload.get("SOURCE", "").strip()
        COMPANY_NAME = vars_payload.get("COMPANY_NAME", "").strip()
        CALL_NUMBER = vars_payload.get("CALL_NUMBER", "").strip()
        ADDRESS = vars_payload.get("ADDRESS", "").strip()
        STATE_NAME = vars_payload.get("STATE_NAME", "").strip()
        LINK = vars_payload.get("LINK", "").strip()
        COMPANY_EMPLOYEE = vars_payload.get("COMPANY_EMPLOYEE", "").strip()
        
        BLOGTYPE = vars_payload.get("BLOGTYPE", "Legal").strip()
        try:
            TEMPERATURE = float(vars_payload.get("TEMPERATURE", 0.70))
        except Exception:
            TEMPERATURE = 0.70

        
        def _coerce_int_list(xs):
            if not xs:
                return []
            out = []
            for x in xs:
                try:
                    out.append(int(x))
                except Exception:
                    continue
            return out

        BLOGFOREXAMPLE_IDS = _coerce_int_list(vars_payload.get("BLOGFOREXAMPLE", []))
        BLOGPART_INTRO_IDS = _coerce_int_list(vars_payload.get("BLOGPART_INTRO", []))
        BLOGPART_FINALCTA_IDS = _coerce_int_list(vars_payload.get("BLOGPART_FINALCTA", []))
        BLOGPART_FAQS_IDS = _coerce_int_list(vars_payload.get("BLOGPART_FAQS", []))
        BLOGPART_BUSINESSDESC_IDS = _coerce_int_list(vars_payload.get("BLOGPART_BUSINESSDESC", []))
        BLOGPART_SHORTCTA_IDS = _coerce_int_list(vars_payload.get("BLOGPART_SHORTCTA", []))

        
        # User-editable prompts (will be pre-filled with defaults but can be edited)
        PROMPT_FULLBLOG = vars_payload.get("PROMPT_FULLBLOG", "").strip()
        PROMPT_INTRO = vars_payload.get("PROMPT_INTRO", "").strip()
        PROMPT_FINALCTA = vars_payload.get("PROMPT_FINALCTA", "").strip()
        PROMPT_FULLFAQS = vars_payload.get("PROMPT_FULLFAQS", "").strip()
        PROMPT_BUSINESSDESC = vars_payload.get("PROMPT_BUSINESSDESC", "").strip()
        PROMPT_REFERENCES = vars_payload.get("PROMPT_REFERENCES", "").strip()
        PROMPT_SHORTCTA = vars_payload.get("PROMPT_SHORTCTA", "").strip()

        # --- Fetch blog examples from database ---
        def fetch_blog_examples(blog_ids, table_name="blogdata", id_column="blogID", text_column="blogText"):
            """
            Fetch blog examples from database and format them.
            Returns formatted string: "Example 1:\n{text}\n\nExample 2:\n{text}..."
            """
            if not blog_ids or len(blog_ids) == 0:
                return ""
            try:
                with db.conn() as conn:
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                        # Safely build query with placeholders
                        placeholders = ','.join(['%s'] * len(blog_ids))
                        query = f"""
                            SELECT {id_column}, {text_column}
                            FROM {table_name}
                            WHERE {id_column} = ANY(%s)
                            ORDER BY {id_column};
                        """
                        cur.execute(query, (blog_ids,))
                        results = cur.fetchall()
                        
                        # Format results
                        examples = []
                        for idx, row in enumerate(results, 1):
                            text = row.get(text_column, "")
                            examples.append(f"Example {idx}:\n{text}")
                        return "\n\n".join(examples)
            except Exception as e:
                app.logger.error(f"Error fetching blog examples: {e}")
                return ""
        def fetch_blog_part_examples(part_ids, column_name):
            """
            Fetch specific blog part examples from blogparts table.
            column_name: 'intro', 'final_cta', 'FAQs', 'business_description', 'short_cta'
            """
            if not part_ids or len(part_ids) == 0:
                return ""
            try:
                with db.conn() as conn:
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                        query = f"""
                            SELECT blogID, {column_name}
                            FROM blogparts
                            WHERE blogID = ANY(%s)
                            ORDER BY blogID;
                        """
                        cur.execute(query, (part_ids,))
                        results = cur.fetchall()
                        
                        # Format results
                        examples = []
                        for idx, row in enumerate(results, 1):
                            text = row.get(column_name, "")
                            examples.append(f"Example {idx}:\n{text}")
                        return "\n\n".join(examples)
            except Exception as e:
                app.logger.error(f"Error fetching blog part examples: {e}")
                return ""
        
        # Fetch all examples from database
        BLOGFOREXAMPLE = fetch_blog_examples(BLOGFOREXAMPLE_IDS)
        BLOGPART_INTRO = fetch_blog_part_examples(BLOGPART_INTRO_IDS, "intro")
        BLOGPART_FINALCTA = fetch_blog_part_examples(BLOGPART_FINALCTA_IDS, "final_cta")
        BLOGPART_FAQS = fetch_blog_part_examples(BLOGPART_FAQS_IDS, "FAQs")
        BLOGPART_BUSINESSDESC = fetch_blog_part_examples(BLOGPART_BUSINESSDESC_IDS, "business_description")
        BLOGPART_SHORTCTA = fetch_blog_part_examples(BLOGPART_SHORTCTA_IDS, "short_cta")

        # --- Replace placeholders in prompts ---
        def replace_vars(prompt_text):
            """Replace {VARIABLE} placeholders with actual values"""
            replacements = {
                "{TITLE}": TITLE,
                "{KEYWORDS}": KEYWORDS,
                "{INSERT_INTRO_QUESTION}": INSERT_INTRO_QUESTION,
                "{INSERT_FAQ_QUESTIONS}": INSERT_FAQ_QUESTIONS,
                "{SOURCE}": SOURCE,
                "{BLOGFOREXAMPLE}": BLOGFOREXAMPLE,
                "{BLOGPART_INTRO}": BLOGPART_INTRO,
                "{BLOGPART_FINALCTA}": BLOGPART_FINALCTA,
                "{BLOGPART_FAQS}": BLOGPART_FAQS,
                "{BLOGPART_BUSINESSDESC}": BLOGPART_BUSINESSDESC,
                "{BLOGPART_SHORTCTA}": BLOGPART_SHORTCTA
            }
            
            result = prompt_text
            for placeholder, value in replacements.items():
                result = result.replace(placeholder, value)
            return result

        # Replace placeholders in all prompts
        PROMPT_FULLBLOG_FINAL = replace_vars(PROMPT_FULLBLOG)
        PROMPT_INTRO_FINAL = replace_vars(PROMPT_INTRO)
        PROMPT_FINALCTA_FINAL = replace_vars(PROMPT_FINALCTA)
        PROMPT_FULLFAQS_FINAL = replace_vars(PROMPT_FULLFAQS)
        PROMPT_BUSINESSDESC_FINAL = replace_vars(PROMPT_BUSINESSDESC)
        PROMPT_REFERENCES_FINAL = replace_vars(PROMPT_REFERENCES)
        PROMPT_SHORTCTA_FINAL = replace_vars(PROMPT_SHORTCTA)

        # --- Call LLM agents ---
        bot_response = callAgents(
            user_message,
            COMPANY_NAME,
            CALL_NUMBER,
            ADDRESS,
            STATE_NAME,
            LINK,
            COMPANY_EMPLOYEE,
            PROMPT_FULLBLOG_FINAL,
            PROMPT_INTRO_FINAL,
            PROMPT_FINALCTA_FINAL,
            PROMPT_FULLFAQS_FINAL,
            PROMPT_BUSINESSDESC_FINAL,
            PROMPT_REFERENCES_FINAL,
            PROMPT_SHORTCTA_FINAL,
            TEMPERATURE
        )
        # Note: Database persistence will be handled by chatbots.py as mentioned
        print("+++++++++++++++++++++++++ BOT RESPONSE +++++++++++++++++++++++++\n", bot_response)
        # Each agent will send its own prompt and bot response to profileHistory
        return jsonify({
            "success": True,
            "response": bot_response,
            "timestamp": datetime.now().isoformat(),
            "debug_info": {
                "blog_type": BLOGTYPE,
                "temperature": TEMPERATURE,
                "examples_fetched": {
                    "full_blogs": len(BLOGFOREXAMPLE_IDS),
                    "intro_parts": len(BLOGPART_INTRO_IDS),
                    "finalcta_parts": len(BLOGPART_FINALCTA_IDS),
                    "faqs_parts": len(BLOGPART_FAQS_IDS),
                    "businessdesc_parts": len(BLOGPART_BUSINESSDESC_IDS),
                    "shortcta_parts": len(BLOGPART_SHORTCTA_IDS)
                }
            }
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
    app.run(host="0.0.0.0", port=10000, debug=False)

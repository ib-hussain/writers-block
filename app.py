# app.py
from __future__ import annotations
import os
import atexit
from datetime import datetime, date
from contextlib import contextmanager
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv
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
# ENV
try:
    load_dotenv()
except Exception:
    pass
SECRET_KEY = os.getenv("SECRET_KEY")
# USER INPUTS 
### PROMPT VARIABLES
TITLE=""
KEYWORDS="lawyer, attorney, consultation, claim, accident, case, insurance, insurance company, evidence, police report, medical records, witness statements, compensation, damages, liability, settlement, legal process, statute limitations, comparative negligence, policy limits, contingency fee, trial, litigation, negotiation, expert witnesses, accident reconstruction, dashcam footage, surveillance footage, medical bills, total loss, gap"
INSERT_INTRO_QUESTION=""
INSERT_INTRO_EXAMPLE=""
INSERT_CTA_EXAMPLE=""
INSERT_FAQ_QUESTIONS=""
SOURCE=""
COMPANY_NAME=""
CALL_NUMBER=""
ADDRESS=""  
STATE_NAME=""
LINK=""
COMPANY_EMPLOYEE=""
#==================================================================================================================================================
# FLASK
app = Flask(
    "Writers Block",
    static_folder="web_files",
    static_url_path="/web_files"
)
app.secret_key = SECRET_KEY
# DB POOL
db = get_db()

# HELPERS(move them to another page later)
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
    You told me "Userprompt" and "chatResponse" are case-sensitive and must be quoted.
    However, your schema.sql shows lower-case userprompt/chatresponse.
    This function detects what actually exists in the database and returns the correct
    column identifiers to select from.
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

        # Prefer exact case-sensitive names if present
        if "Userprompt" in colset and "chatResponse" in colset:
            return '"Userprompt"', '"chatResponse"'

        # Fallback to lowercase (most likely)
        if "userprompt" in colset and "chatresponse" in colset:
            return "userprompt", "chatresponse"

        # If schema is inconsistent, fail with a precise error
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

    Performance notes:
      - Avoid COUNT(*) (slow on large tables); use len(rows)
      - Avoid ORDER BY unless you know an indexed key
    """
    excluded = {"profilehistory"}
    try:
        req = (table_name or "").strip()
        if not req:
            return json_error("MISSING_TABLE", "Missing table_name in URL path.", 400)
        with db.conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Validate table name exists in public schema (prevents SQL injection via identifiers)
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
                # Columns
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema='public' AND table_name=%s
                    ORDER BY ordinal_position;
                """, (actual_name,))
                columns = [r["column_name"] for r in cur.fetchall()]
                # Full rows (no ORDER BY, no LIMIT)
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
            # detect correct profileHistory prompt/response columns
            user_col, resp_col = get_profilehistory_columns(conn)

            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Note: we must inject identifiers safely: only from controlled values returned above
                sql = f"""
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
                cur.execute(sql)
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
                # Force a stable output order and stable JSON keys
                sql = f"""
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
                cur.execute(sql, (parsed_date,))
                rows = cur.fetchall()
                if not rows:
                    # Diagnostics: prove whether data exists but entry_date alignment differs
                    # (timezone boundary issues / entry_date population issues)
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
@app.route('/api/chat', methods=['POST'])
def handle_chat():
    """
    Handle chatbot messages.
    Stores user prompt and generated response in profileHistory.
    Marks progress.chat as TRUE for today.
    """
    try:
        # Parse request
        data = request.get_json()
        if not data:
            return json_error("NO_DATA", "No JSON data provided", 400)
        user_message = data.get('message', '').strip()
        if not user_message:
            return json_error("EMPTY_MESSAGE", "Message cannot be empty", 400)
        # Generate response (placeholder for now - integrate with your LLM)
        bot_response = f"Echo: {user_message}"
        # issue: change the above later and integrate with LLM model to get actual response but this is like this for testing right now
        # issue: change the below later and this is like this for testing right now
        # # Store in database
        # with db.conn() as conn:
        #     # Get correct column names
        #     user_col, resp_col = get_profilehistory_columns(conn)
            
        #     with conn.cursor() as cur:
        #         # Insert into profileHistory
        #         # Using parameterized query for safety
        #         sql = f"""
        #             INSERT INTO profileHistory (entry_date, entry, {user_col}, {resp_col})
        #             VALUES (CURRENT_DATE, CURRENT_TIMESTAMP, %s, %s)
        #             RETURNING id;
        #         """
        #         cur.execute(sql, (user_message, bot_response))
        #         inserted_id = cur.fetchone()[0]
        #         conn.commit()
        
        # Return success with response
        return jsonify({
            "success": True,
            "response": bot_response,
            # "message_id": inserted_id,
            "timestamp": datetime.now().isoformat()
        }), 200
    except PoolError as e:
        return json_error("POOL_EXHAUSTED", "Database connection pool exhausted", 500, details=str(e))
    except Exception as e:
        app.logger.error(f"Chat endpoint error: {e}")
        return json_error("CHAT_FAILED", "Failed to process chat message", 500, details=str(e))

# MAIN (local dev)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=DEBUGGING_MODE)

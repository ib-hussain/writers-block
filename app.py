# app.py
from __future__ import annotations

import os
import atexit
from datetime import datetime, date
from contextlib import contextmanager
from typing import Dict, Any, List, Optional, Tuple

from dotenv import load_dotenv
from flask import Flask, jsonify, request, redirect

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool, PoolError

# -----------------------------------------------------------------------------
# ENV
# -----------------------------------------------------------------------------
try:
    load_dotenv()
except Exception:
    pass

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

if not DATABASE_URL:
    # Fail fast with a clear error rather than mysterious DB failures later.
    raise RuntimeError("DATABASE_URL is not set. Put it in your .env file.")

# -----------------------------------------------------------------------------
# FLASK
# -----------------------------------------------------------------------------
app = Flask(
    __name__,
    static_folder="web_files",
    static_url_path="/web_files"
)
app.secret_key = SECRET_KEY
# -----------------------------------------------------------------------------
# DB POOL
# -----------------------------------------------------------------------------
# Keep pool small in local dev; Supabase can also enforce limits.
POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))
# psycopg2's pool accepts kwargs for connect(). Use sslmode=require for Supabase.
pool = SimpleConnectionPool(
    minconn=POOL_MIN,
    maxconn=POOL_MAX,
    dsn=DATABASE_URL,
    sslmode="require"
    )
@atexit.register
def _close_pool():
    try:
        pool.closeall()
    except Exception:
        pass
@contextmanager
def db_conn():
    """
    Correct pattern for psycopg2 connection pools:
    - borrow with getconn()
    - ALWAYS return with putconn()
    - rollback any open transaction state on return
    """
    conn = None
    try:
        conn = pool.getconn()
        yield conn
    finally:
        if conn is not None:
            try:
                # ensure connection is clean for the next borrower
                if conn.closed == 0:
                    conn.rollback()
            except Exception:
                pass
            try:
                pool.putconn(conn)
            except Exception:
                pass
# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
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
# -----------------------------------------------------------------------------
# BASIC PAGES
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    return redirect("/web_files/chatbot.html")
@app.route("/databaseView")
def database_view_page():
    return redirect("/web_files/databaseView.html")
@app.route("/profile")
def profile_page():
    return redirect("/web_files/profile.html")
# -----------------------------------------------------------------------------
# API: TABLES
# -----------------------------------------------------------------------------
@app.route("/api/db/tables")
def api_db_tables():
    limit = request.args.get("limit", default=200, type=int)
    limit = clamp_int(limit, 1, 2000)
    excluded = {"profilehistory"}  # exclude profileHistory by requirement
    try:
        with db_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT tablename
                    FROM pg_catalog.pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY tablename ASC;
                """)
                table_names = [r["tablename"] for r in cur.fetchall()]
                table_names = [t for t in table_names if t.lower() not in excluded]
                tables_payload = []
                for t in table_names:
                    # Columns
                    cur.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema='public' AND table_name=%s
                        ORDER BY ordinal_position;
                    """, (t,))
                    columns = [r["column_name"] for r in cur.fetchall()]
                    # Total count
                    cur.execute(f'SELECT COUNT(*) AS cnt FROM "{t}";')
                    row_count = int(cur.fetchone()["cnt"])
                    # Rows
                    cur.execute(f'SELECT * FROM "{t}" ORDER BY 1 ASC LIMIT %s;', (limit,))
                    rows = cur.fetchall()

                    tables_payload.append({
                        "name": t,
                        "columns": columns,
                        "row_count": row_count,
                        "rows": rows
                    })
        return jsonify({"success": True, "tables": tables_payload}), 200
    except PoolError as e:
        return json_error(
            "POOL_EXHAUSTED",
            "DB connection pool exhausted. This indicates connections are not being returned correctly.",
            500,
            details=str(e),
            hint="Ensure all DB access goes through db_conn() context manager."
        )
    except Exception as e:
        return json_error("DB_TABLES_FAIL", "Failed to load tables.", 500, details=str(e))
# -----------------------------------------------------------------------------
# API: TOKENS (WORDS) PER DAY FOR CURRENT MONTH
# -----------------------------------------------------------------------------
@app.route("/api/stats/tokens/month")
def api_tokens_month():
    try:
        with db_conn() as conn:
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
# -----------------------------------------------------------------------------
# API: PROFILE HISTORY BY DATE
# -----------------------------------------------------------------------------
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
        with db_conn() as conn:
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

# -----------------------------------------------------------------------------
# MAIN (local dev)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Keep host/port aligned with your usage: 127.0.0.1:10000
    app.run(host="127.0.0.1", port=10000, debug=True)

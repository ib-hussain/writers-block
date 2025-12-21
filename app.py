# library includes #################################################################################################################################
from dotenv import load_dotenv
try: load_dotenv()
except: pass
import os
from datetime import time as dt_time, datetime
from decimal import Decimal
from flask import (
    Flask, jsonify, request, send_from_directory,
    redirect, url_for, session,abort
)
import psycopg2
from psycopg2.pool import SimpleConnectionPool
import psycopg2.extras
from psycopg2.extras import RealDictCursor
from tempfile import NamedTemporaryFile
# header includes  #################################################################################################################################
# from data.database_postgres import ()
# from chatbots.diet import get_image_description
# from chatbots.reasoning import respond 
# SETUP            #################################################################################################################################
app = Flask(
    "Writer's Block",
    static_folder="web_files",
    static_url_path="/web_files"
)
app.secret_key = os.getenv("SECRET_KEY")  # Important for sessions

# API CALLS        #################################################################################################################################
@app.route('/')
def index():
    return redirect('/web_files/chatbot.html')
    
@app.route("/databaseView")
def database_view_page():
    return redirect('/web_files/databaseView.html')

@app.route("/profile")
def profile_page():
    return redirect('/web_files/profile.html')
# issue: make this function and put it in the backend file of database_postgres.py 
pool = SimpleConnectionPool(
        minconn=1,
        maxconn=5,
        dsn=os.getenv("DATABASE_URL"),
        sslmode="require"
    )
def get_db_conn():
    return pool.getconn()
def release_db_conn(conn):
    pool.putconn(conn)

@app.route("/api/db/tables")
def api_db_tables():
    limit = request.args.get("limit", default=200, type=int)
    limit = max(1, min(limit, 2000))  # safety

    excluded = {"profilehistory"}

    with get_db_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # List public tables
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

            return jsonify({"tables": tables_payload})

@app.route("/api/stats/tokens/month")
def api_tokens_month():
    with get_db_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # Daily word counts for current month
            # word proxy: count whitespace-separated tokens
            cur.execute("""
                WITH daily AS (
                    SELECT
                        entry_date,
                        COALESCE(
                            SUM(
                                CASE
                                  WHEN "userprompt" IS NULL OR btrim("userprompt") = '' THEN 0
                                  ELSE array_length(regexp_split_to_array(btrim("userprompt"), '\\s+'), 1)
                                END
                            ), 0
                        ) AS input_words,
                        COALESCE(
                            SUM(
                                CASE
                                  WHEN "chatresponse" IS NULL OR btrim("chatresponse") = '' THEN 0
                                  ELSE array_length(regexp_split_to_array(btrim("chatresponse"), '\\s+'), 1)
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
            """)

            daily = cur.fetchall()

            cur.execute("SELECT to_char(CURRENT_DATE, 'Mon YYYY') AS month_label;")
            month_label = cur.fetchone()["month_label"]

            return jsonify({
                "month_label": month_label,
                "daily": daily
            })

@app.route("/api/profile/history")
def api_profile_history_by_date():
    d = request.args.get("date", "").strip()
    if not d:
        abort(400, description="Missing date parameter (YYYY-MM-DD).")

    # Robust parse: accepts YYYY-MM-DD only
    try:
        parsed_date = datetime.strptime(d, "%Y-%m-%d").date()
    except ValueError:
        abort(400, description="Invalid date format. Use YYYY-MM-DD.")

    with get_db_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, entry_date, entry, "userprompt", "chatresponse"
                FROM profileHistory
                WHERE entry_date = %s
                ORDER BY id ASC;
            """, (parsed_date,))
            rows = cur.fetchall()

    return jsonify({"rows": rows, "date": d})

# ////











# ---------- NEW: text-only respond(prompt) returning markdown ----------
@app.route('/api/respond', methods=['POST'])
def api_respond():
    """
    Expects JSON: { "prompt": "<text>" }
    Calls respond(prompt) which returns markdown string.
    Returns { success: True, markdown: "<md>" } or { success: False, error: "<msg>" }.
    """
    if not request.is_json:
        return jsonify({'success': False, 'error': 'JSON body required'}), 400
    data = request.get_json(silent=True) or {}
    prompt = (data.get('prompt') or '').strip()
    if respond is None:
        return jsonify({'success': False, 'error': 'respond function not configured'}), 500
    try:
        markdown = respond(prompt)
    except TypeError:
        # If the function signature is different, try positional
        markdown = respond(prompt)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    if not isinstance(markdown, str):
        return jsonify({'success': False, 'error': 'respond() did not return a string'}), 500
    return jsonify({'success': True, 'markdown': markdown})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
    
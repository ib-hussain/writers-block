from __future__ import annotations
import os
from datetime import datetime
from flask import Flask, jsonify, request, redirect
from psycopg2 import sql
import psycopg2
import psycopg2.extras
from psycopg2.pool import PoolError

from chatbots.orchestrater import callAgents
from data.database_postgres import get_db, json_error, parse_yyyy_mm_dd, get_profilehistory_columns

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

DEBUGGING_MODE = True
SECRET_KEY = os.getenv("SECRET_KEY")

app = Flask(
    "Writer's Block",
    static_folder="web_files",
    static_url_path="/web_files"
)
app.secret_key = SECRET_KEY

db = get_db()


@app.route("/")
def index():
    return redirect("/web_files/chatbot.html")


@app.route("/api/db/table/<table_name>")
def api_db_table(table_name: str):
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

        # Important: rows may be empty; frontend will show default message
        return jsonify({"success": True, "code": "OK", "date": d, "rows": rows}), 200

    except PoolError as e:
        return json_error("POOL_EXHAUSTED", "DB pool exhausted.", 500, details=str(e))
    except Exception as e:
        return json_error("PROFILE_HISTORY_FAIL", "Failed to load profile history.", 500, details=str(e))


@app.route('/api/chat', methods=['POST'])
def handle_chat():
    """
    Chat endpoint:
    - Reads user message + vars from frontend
    - Fetches examples (RAG-lite) from DB once
    - Substitutes placeholders inside prompt templates
    - Calls orchestrator
    """
    try:
        data = request.get_json(silent=True) or {}
        user_message = (data.get("message") or "").strip()
        vars_payload = data.get("vars") or {}
        if not user_message:
            return json_error("EMPTY_MESSAGE", "Message cannot be empty", 400)

        # Extract vars
        TITLE = (vars_payload.get("TITLE") or "").strip()
        KEYWORDS = (vars_payload.get("KEYWORDS") or "").strip()
        INSERT_INTRO_QUESTION = (vars_payload.get("INSERT_INTRO_QUESTION") or "").strip()
        INSERT_FAQ_QUESTIONS = (vars_payload.get("INSERT_FAQ_QUESTIONS") or "").strip()
        SOURCE = (vars_payload.get("SOURCE") or "").strip()
        COMPANY_NAME = (vars_payload.get("COMPANY_NAME") or "").strip()
        CALL_NUMBER = (vars_payload.get("CALL_NUMBER") or "").strip()
        ADDRESS = (vars_payload.get("ADDRESS") or "").strip()
        STATE_NAME = (vars_payload.get("STATE_NAME") or "").strip()
        LINK = (vars_payload.get("LINK") or "").strip()
        COMPANY_EMPLOYEE = (vars_payload.get("COMPANY_EMPLOYEE") or "").strip()

        BLOGTYPE = (vars_payload.get("BLOGTYPE") or "Legal").strip()
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

        PROMPT_FULLBLOG = (vars_payload.get("PROMPT_FULLBLOG") or "").strip()
        PROMPT_INTRO = (vars_payload.get("PROMPT_INTRO") or "").strip()
        PROMPT_FINALCTA = (vars_payload.get("PROMPT_FINALCTA") or "").strip()
        PROMPT_FULLFAQS = (vars_payload.get("PROMPT_FULLFAQS") or "").strip()
        PROMPT_BUSINESSDESC = (vars_payload.get("PROMPT_BUSINESSDESC") or "").strip()
        PROMPT_REFERENCES = (vars_payload.get("PROMPT_REFERENCES") or "").strip()
        PROMPT_SHORTCTA = (vars_payload.get("PROMPT_SHORTCTA") or "").strip()

        # -----------------------------
        # DB: fetch examples once
        # -----------------------------
        def fetch_blog_examples(blog_ids, table_name="blogdata", id_column="blogID", text_column="blogText"):
            if not blog_ids:
                return ""
            try:
                with db.conn() as conn:
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                        query = f"""
                            SELECT {id_column}, {text_column}
                            FROM {table_name}
                            WHERE {id_column} = ANY(%s)
                            ORDER BY {id_column};
                        """
                        cur.execute(query, (blog_ids,))
                        results = cur.fetchall()

                        examples = []
                        for idx, row in enumerate(results, 1):
                            text = row.get(text_column, "") or ""
                            examples.append(f"Example {idx}:\n{text}")
                        return "\n\n".join(examples)
            except Exception as e:
                app.logger.error(f"Error fetching blog examples: {e}")
                return ""

        def fetch_blog_part_examples(part_ids, column_name):
            if not part_ids:
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

                        examples = []
                        for idx, row in enumerate(results, 1):
                            text = row.get(column_name, "") or ""
                            examples.append(f"Example {idx}:\n{text}")
                        return "\n\n".join(examples)
            except Exception as e:
                app.logger.error(f"Error fetching blog part examples ({column_name}): {e}")
                return ""

        BLOGFOREXAMPLE = fetch_blog_examples(BLOGFOREXAMPLE_IDS)
        BLOGPART_INTRO = fetch_blog_part_examples(BLOGPART_INTRO_IDS, "intro")
        BLOGPART_FINALCTA = fetch_blog_part_examples(BLOGPART_FINALCTA_IDS, "final_cta")
        BLOGPART_FAQS = fetch_blog_part_examples(BLOGPART_FAQS_IDS, "FAQs")
        BLOGPART_BUSINESSDESC = fetch_blog_part_examples(BLOGPART_BUSINESSDESC_IDS, "business_description")
        BLOGPART_SHORTCTA = fetch_blog_part_examples(BLOGPART_SHORTCTA_IDS, "short_cta")

        # -----------------------------
        # Replace placeholders in prompts
        # -----------------------------
        def replace_vars(prompt_text: str) -> str:
            prompt_text = prompt_text or ""
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
                "{BLOGPART_SHORTCTA}": BLOGPART_SHORTCTA,
            }
            result = prompt_text
            for placeholder, value in replacements.items():
                result = result.replace(placeholder, value or "")
            return result

        PROMPT_FULLBLOG_FINAL = replace_vars(PROMPT_FULLBLOG)
        PROMPT_INTRO_FINAL = replace_vars(PROMPT_INTRO)
        PROMPT_FINALCTA_FINAL = replace_vars(PROMPT_FINALCTA)
        PROMPT_FULLFAQS_FINAL = replace_vars(PROMPT_FULLFAQS)
        PROMPT_BUSINESSDESC_FINAL = replace_vars(PROMPT_BUSINESSDESC)
        PROMPT_REFERENCES_FINAL = replace_vars(PROMPT_REFERENCES)
        PROMPT_SHORTCTA_FINAL = replace_vars(PROMPT_SHORTCTA)

        # -----------------------------
        # Debug summary (no giant prompt dumps)
        # -----------------------------
        print("\n[API] /api/chat received request")
        print(f"[API] BLOGTYPE={BLOGTYPE} | TEMPERATURE={TEMPERATURE}")
        print(f"[API] user_message chars={len(user_message)}")
        print(f"[API] examples fetched: full={len(BLOGFOREXAMPLE_IDS)} intro={len(BLOGPART_INTRO_IDS)} finalcta={len(BLOGPART_FINALCTA_IDS)} faqs={len(BLOGPART_FAQS_IDS)} bizdesc={len(BLOGPART_BUSINESSDESC_IDS)} shortcta={len(BLOGPART_SHORTCTA_IDS)}")
        print(f"[API] prompt sizes: fullblog={len(PROMPT_FULLBLOG_FINAL)} intro={len(PROMPT_INTRO_FINAL)} faqs={len(PROMPT_FULLFAQS_FINAL)}")

        # -----------------------------
        # Call orchestrator
        # -----------------------------
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

        # Debug: print only a short preview
        preview = (bot_response[:450] + "…") if bot_response and len(bot_response) > 450 else bot_response
        print("[API] ✅ BOT RESPONSE PREVIEW:\n", preview, "\n")

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)

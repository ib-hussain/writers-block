'''
db.py (its name here is database_postgres.py)
Database handler for the project.
This header provides functions to interact with the PostgreSQL database.
'''
from __future__ import annotations
import os
import atexit
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple
import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool, PoolError
from datetime import datetime, date
from flask import jsonify

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

class DB:
    """
    Centralised DB manager for psycopg2 + SimpleConnectionPool.
    Guarantees:
      - No connection leaks (always returns to pool)
      - Clean connection state (rollback) before reuse
    """
    def __init__(self, dsn: str, minconn: int = POOL_MIN, maxconn: int = POOL_MAX, sslmode: str = "require"):
        if not dsn:
            raise RuntimeError("DATABASE_URL is missing.")
        # Note: psycopg2 supports connect kwargs via pool constructor.
        self.pool = SimpleConnectionPool(minconn=minconn, maxconn=maxconn, dsn=dsn, sslmode=sslmode)
        atexit.register(self.close_all)
    def close_all(self) -> None:
        try:
            self.pool.closeall()
        except Exception:
            pass
    @contextmanager
    def conn(self):
        c = None
        try:
            c = self.pool.getconn()
            yield c
        finally:
            if c is not None:
                try:
                    if c.closed == 0:
                        # Ensure no open transaction leaks into next borrower.
                        c.rollback()
                except Exception:
                    pass
                try:
                    self.pool.putconn(c)
                except Exception:
                    pass
    def fetchall(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        with self.conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                return cur.fetchall()
    def fetchone(self, query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        with self.conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                return cur.fetchone()
    def execute(self, query: str, params: Optional[tuple] = None) -> None:
        with self.conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()

# Singleton instance holder (created by init_db)
_db: Optional[DB] = None
def init_db() -> DB:
    global _db
    if _db is not None:
        return _db
    dsn = os.getenv("DATABASE_URL")
    minc = POOL_MIN
    maxc = POOL_MAX
    _db = DB(dsn=dsn, minconn=minc, maxconn=maxc, sslmode="require")
    return _db
def get_db() -> DB:
    if _db is None:
        return init_db()
    return _db
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

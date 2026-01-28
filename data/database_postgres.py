'''
db.py (its name here is database_postgres.py)
Database handler for the project.
This header provides functions to interact with the PostgreSQL database.
'''
from __future__ import annotations

import os
import atexit
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool, PoolError
from datetime import datetime, date
from flask import jsonify

# -----------------------------
# CONFIG
# -----------------------------
DEBUGGING_MODE = True

POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))

# Keepalive defaults (helps prevent "server closed the connection unexpectedly")
KEEPALIVES = int(os.getenv("DB_KEEPALIVES", "1"))
KEEPALIVES_IDLE = int(os.getenv("DB_KEEPALIVES_IDLE", "30"))
KEEPALIVES_INTERVAL = int(os.getenv("DB_KEEPALIVES_INTERVAL", "10"))
KEEPALIVES_COUNT = int(os.getenv("DB_KEEPALIVES_COUNT", "5"))

# Singleton instance holder
_db: Optional["DB"] = None


class DB:
    """
    Centralised DB manager for psycopg2 + SimpleConnectionPool.

    Guarantees:
      - No connection leaks (always returns to pool)
      - Clean connection state (rollback) before reuse
      - Validates connection before handing it out
      - Uses TCP keepalives to reduce unexpected disconnects
    """
    def __init__(self, dsn: str, minconn: int = POOL_MIN, maxconn: int = POOL_MAX, sslmode: str = "require"):
        if not dsn:
            raise RuntimeError("DATABASE_URL is missing.")

        self.dsn = dsn
        self.sslmode = sslmode

        # SimpleConnectionPool forwards kwargs to psycopg2.connect
        self.pool = SimpleConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            dsn=dsn,
            sslmode=sslmode,
            keepalives=KEEPALIVES,
            keepalives_idle=KEEPALIVES_IDLE,
            keepalives_interval=KEEPALIVES_INTERVAL,
            keepalives_count=KEEPALIVES_COUNT,
        )
        atexit.register(self.close_all)

    def close_all(self) -> None:
        try:
            self.pool.closeall()
        except Exception:
            pass

    def _is_conn_healthy(self, conn) -> bool:
        try:
            if conn is None:
                return False
            if getattr(conn, "closed", 1) != 0:
                return False
            # Cheap ping (no locks, minimal overhead)
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
            return True
        except Exception:
            return False

    @contextmanager
    def conn(self):
        """
        Borrow a connection from the pool, ensure it's healthy, and return it safely.
        """
        c = None
        try:
            c = self.pool.getconn()

            # Validate
            if not self._is_conn_healthy(c):
                try:
                    # Drop broken conn from pool, create a new one manually
                    try:
                        self.pool.putconn(c, close=True)
                    except Exception:
                        pass
                    c = psycopg2.connect(
                        dsn=self.dsn,
                        sslmode=self.sslmode,
                        keepalives=KEEPALIVES,
                        keepalives_idle=KEEPALIVES_IDLE,
                        keepalives_interval=KEEPALIVES_INTERVAL,
                        keepalives_count=KEEPALIVES_COUNT,
                    )
                except Exception as e:
                    raise RuntimeError(f"DB reconnection failed: {e}")

            yield c

        finally:
            if c is not None:
                try:
                    if c.closed == 0:
                        # Ensure no open transaction leaks into next borrower
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


def init_db() -> DB:
    global _db
    if _db is not None:
        return _db

    dsn = os.getenv("DATABASE_URL")
    _db = DB(dsn=dsn, minconn=POOL_MIN, maxconn=POOL_MAX, sslmode=os.getenv("DB_SSLMODE", "require"))
    return _db


def get_db() -> DB:
    if _db is None:
        return init_db()
    return _db


# -----------------------------
# HELPERS
# -----------------------------
def json_error(code: str, message: str, http_status: int = 500, **extra):
    payload = {"success": False, "code": code, "message": message}
    if extra:
        payload.update(extra)
    return jsonify(payload), http_status


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

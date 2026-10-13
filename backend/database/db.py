"""
database/db.py
----------------
Manages the PostgreSQL connection using a small connection pool
(rather than opening a brand-new connection on every request, which
is slow and doesn't scale). All credentials come from environment
variables (see backend/.env) — nothing is hardcoded here.
"""

import os
import psycopg2
from psycopg2 import pool

_connection_pool = None


class DatabaseError(Exception):
    """Raised when the database is unavailable or a query fails."""
    pass


def init_pool():
    """
    Creates the connection pool. Call this once at app startup.
    Raises DatabaseError immediately if PostgreSQL is unreachable —
    we want to know that at startup, not on the first user request.
    """
    global _connection_pool

    try:
        _connection_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "digit_recognition"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )
    except psycopg2.OperationalError as exc:
        raise DatabaseError(
            f"Could not connect to PostgreSQL: {exc}. "
            f"Check that PostgreSQL is running and the DB_* values in backend/.env are correct."
        ) from exc

    return _connection_pool


def get_connection():
    if _connection_pool is None:
        raise DatabaseError("Database pool is not initialized. init_pool() must be called at app startup.")
    try:
        return _connection_pool.getconn()
    except psycopg2.pool.PoolError as exc:
        raise DatabaseError(f"Could not get a database connection: {exc}") from exc


def release_connection(conn):
    if _connection_pool is not None and conn is not None:
        _connection_pool.putconn(conn)


def ping() -> bool:
    """Cheap liveness check used by GET /health."""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        return True
    except Exception:
        return False
    finally:
        release_connection(conn)

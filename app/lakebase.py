"""
Lakebase (Databricks-managed Postgres) connection helper.

Uses a single LAKEBASE_URL secret from the restaurant-app scope
(a standard Postgres connection URL, e.g.
postgresql://role:password@host:5432/main?sslmode=require).

Pattern adapted from databricks-lakebase-app-day-3/dashboard/lakebase.py
"""

import base64
import os
from contextlib import contextmanager

import psycopg2
from databricks.sdk import WorkspaceClient
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine

_w = WorkspaceClient()

_SCOPE = os.environ.get("LAKEBASE_SECRET_SCOPE", "restaurant-app")
_KEY = os.environ.get("LAKEBASE_SECRET_KEY", "lakebase-url")


def _lakebase_url() -> str:
    """Fetch and decode the Lakebase connection URL from the Databricks secret scope."""
    secret = _w.secrets.get_secret(scope=_SCOPE, key=_KEY)
    return base64.b64decode(secret.value).decode("utf-8")


@contextmanager
def get_connection():
    """Yield a raw psycopg2 connection with a RealDictCursor factory.
    
    Usage:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM restaurants LIMIT 10")
                results = cur.fetchall()
    """
    conn = psycopg2.connect(_lakebase_url(), cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()


def get_engine():
    """Return a SQLAlchemy engine for Lakebase.
    
    Usage:
        engine = get_engine()
        df = pd.read_sql("SELECT * FROM restaurants", engine)
    """
    return create_engine(_lakebase_url())


def run_query(sql: str, params: tuple | dict | None = None) -> list[dict]:
    """Run a read query against Lakebase and return rows as list[dict].
    
    Args:
        sql: SQL query string
        params: Query parameters (tuple for %s, dict for %(name)s)
    
    Returns:
        List of rows as dictionaries
    
    Example:
        restaurants = run_query(
            "SELECT * FROM restaurants WHERE rating >= %s LIMIT %s",
            (4.0, 10)
        )
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def run_write(sql: str, params: tuple | dict | None = None) -> int:
    """Run an INSERT/UPDATE/DELETE against Lakebase, return affected row count.
    
    Args:
        sql: SQL statement string
        params: Query parameters (tuple for %s, dict for %(name)s)
    
    Returns:
        Number of affected rows
    
    Example:
        row_count = run_write(
            "INSERT INTO saved_restaurants (user_id, restaurant_id) VALUES (%s, %s)",
            ("user@example.com", "rest_123")
        )
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount


# Backward compatibility aliases for existing code
def get_db_connection():
    """Deprecated: Use get_connection() context manager instead.
    
    Returns a raw connection (not a context manager).
    Caller is responsible for closing the connection.
    """
    return psycopg2.connect(_lakebase_url(), cursor_factory=RealDictCursor)


def execute_query(query: str, params=None, fetch=True):
    """Deprecated: Use run_query() or run_write() instead.
    
    Provided for backward compatibility with db_helper.py pattern.
    """
    if fetch:
        return run_query(query, params)
    else:
        run_write(query, params)
        return None

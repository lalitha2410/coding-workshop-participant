# ============================================================
# GENERATED FILE - DO NOT EDIT
# Source of truth: backend/_shared/postgres_service.py
# Regenerate with: bin/sync-shared.sh
# ============================================================
"""
Shared PostgreSQL connection management for backend services.

Canonical source of truth. This module is propagated into each backend service
folder by bin/sync-shared.sh so every Lambda bundles its own copy (each service
is packaged only from its own directory). Edit this file — never the generated
copies under backend/<service>/postgres_service.py.

Reuses a module-level connection across warm Lambda invocations (psycopg3),
following the connection-pooling pattern from the workshop example. The config
is built once from POSTGRES_* env vars, with local defaults, and switches on
SSL for cloud (Aurora) when IS_LOCAL is not "true".
"""

import os
from psycopg import connect
from psycopg.rows import dict_row

# Module-level connection reused across invocations within the same container.
# Persists between invocations; reset to None on failure to force a reconnect.
PG_CONN = None


def _build_config():
    """Build the psycopg3 connection string from POSTGRES_* environment variables."""
    is_local = os.getenv("IS_LOCAL", "false") == "true"
    config = (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"user={os.getenv('POSTGRES_USER', 'postgres')} "
        f"password={os.getenv('POSTGRES_PASS', 'postgres123')} "
        f"dbname={os.getenv('POSTGRES_NAME', 'projectdb')} "
        f"connect_timeout=15"
    )
    # Cloud (Aurora) requires SSL; local Postgres runs without it.
    if not is_local:
        config += " sslmode=require"
    return config


# Built once at module load and reused across invocations.
PG_CONFIG = _build_config()


def _get_connection():
    """Return the pooled connection, (re)connecting if missing or closed."""
    global PG_CONN
    if PG_CONN is None or PG_CONN.closed:
        PG_CONN = connect(PG_CONFIG, row_factory=dict_row)
    return PG_CONN


def execute(sql, params=None, fetch=None):
    """
    Execute a SQL statement on the pooled connection and commit.

    Args:
        sql (str): Parameterized SQL (use %s placeholders — never string interpolation).
        params (tuple | list, optional): Values bound to the placeholders.
        fetch (str, optional): None -> return nothing; "one" -> a single row dict
            (or None); "all" -> a list of row dicts.

    Returns:
        dict | list | None: Rows as dicts, depending on `fetch`.

    On error the transaction is rolled back so the connection stays usable; if
    the connection itself is broken it is reset to None to force a reconnect.
    """
    global PG_CONN
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            result = None
            if fetch == "one":
                result = cur.fetchone()
            elif fetch == "all":
                result = cur.fetchall()
        conn.commit()
        return result
    except Exception:
        # Recoverable query error: roll back and keep the connection.
        # Broken connection: drop it so the next call reconnects cleanly.
        if PG_CONN is not None and not PG_CONN.closed:
            try:
                PG_CONN.rollback()
            except Exception:
                PG_CONN = None
        else:
            PG_CONN = None
        raise

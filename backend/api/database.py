from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Dict, Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from backend.api.config import get_settings

logger = logging.getLogger(__name__)

_ENGINE_CACHE: Dict[str, Engine] = {}

# ---------------------------------------------------------------------------
# Supabase / PostgreSQL helper text shown in connection errors
# ---------------------------------------------------------------------------
_SUPABASE_HELP = """
Troubleshooting checklist:
  1. Is your Supabase project ACTIVE (not paused)?
     → Go to app.supabase.com and check the project status.
       Free-tier projects pause after ~1 week of inactivity.
       Click "Restore project" if it is paused.

  2. Are you using the SESSION POOLER URL?
     The direct URL (db.xxx.supabase.co:5432) requires IPv6 and
     often fails on home/office networks.
     Use the Session Pooler URL instead:

     In Supabase → Project Settings → Database → Connection string
     ➜ Select "Session pooler" tab (port 5432 via pooler.supabase.com)

     It looks like:
       postgresql://postgres.PROJECTREF:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres

  3. Check that your password is correct and has no special characters
     that need URL-encoding (@ % # etc.).

  4. If using a custom Postgres host, verify the host is reachable:
       ping <your-host>
"""


# ---------------------------------------------------------------------------
# Driver resolution
# ---------------------------------------------------------------------------

def _resolve_connection_string(conn_str: str) -> str:
    """
    Ensure the connection string uses an *installed* SQLAlchemy dialect driver.

    Priority order for PostgreSQL:
      1. Keep whatever the user explicitly specified (postgresql+psycopg2://, etc.)
      2. Try psycopg2  (psycopg2-binary — most commonly installed)
      3. Try psycopg   (v3)
      4. Try pg8000    (pure-Python fallback)
      5. Return as-is  (let SQLAlchemy surface a descriptive error)

    This prevents 'Can't load plugin: sqlalchemy.dialects:postgresql.psycopg'
    when psycopg v3 is not installed.
    """
    try:
        url = make_url(conn_str)
        backend    = url.get_backend_name()   # 'postgresql', 'sqlite', …
        drivername = url.drivername           # 'postgresql' or 'postgresql+psycopg2'

        if backend not in {"postgresql", "postgres"}:
            return conn_str                   # Not postgres — leave untouched

        # User already pinned an explicit driver (except psycopg v3 which may be missing)
        if "+" in drivername and not drivername.endswith("+psycopg"):
            return conn_str

        # Probe in preference order
        for candidate in ("psycopg2", "psycopg", "pg8000"):
            try:
                __import__(candidate.replace("-", "_"))
                resolved = str(url.set(drivername=f"postgresql+{candidate}"))
                logger.info("PostgreSQL driver → '%s'  (host: %s)", candidate, url.host)
                return resolved
            except ImportError:
                continue

        logger.warning(
            "No PostgreSQL driver found (tried psycopg2, psycopg, pg8000). "
            "Install one with:  pip install psycopg2-binary"
        )
        return conn_str

    except Exception:  # noqa: BLE001
        return conn_str  # URL parsing failed — return as-is


# ---------------------------------------------------------------------------
# Engine factory
# ---------------------------------------------------------------------------

def get_engine(connection_string: Optional[str] = None) -> Engine:
    """
    Return a cached SQLAlchemy Engine for the given connection string.

    The engine is created lazily — no TCP connection is made until the first
    query.  This allows the server to start even if the DB is temporarily
    unreachable, and surfaces connection errors at query-time with clear
    guidance.
    """
    settings = get_settings()
    raw = connection_string or settings.database.connection_string
    if not raw:
        raise ValueError(
            "Database connection string is required. "
            "Set it in config.yml → database.connection_string "
            "or via the DATABASE_URL environment variable."
        )

    resolved = _resolve_connection_string(raw)

    if resolved not in _ENGINE_CACHE:
        connect_args: dict = {}
        if _is_postgres(resolved):
            connect_args = {
                "connect_timeout": 10,                   # fail fast on unreachable host
                "options": "-c statement_timeout=30000", # 30 s per-query timeout
            }

        engine = create_engine(
            resolved,
            pool_pre_ping=True,                  # drop stale connections automatically
            pool_size=settings.database.pool_size,
            pool_timeout=settings.database.pool_timeout,
            pool_recycle=1800,                   # recycle connections every 30 min
            connect_args=connect_args,
        )
        _ENGINE_CACHE[resolved] = engine
        logger.info("Engine registered (lazy) for host: %s", _safe_host(resolved))

    return _ENGINE_CACHE[resolved]


def _is_postgres(conn_str: str) -> bool:
    return conn_str.startswith("postgresql") or conn_str.startswith("postgres")


def _safe_host(conn_str: str) -> str:
    """Return host:port only — never log credentials."""
    try:
        url = make_url(conn_str)
        return f"{url.host}:{url.port}"
    except Exception:
        return "<unknown>"


# ---------------------------------------------------------------------------
# Connection context manager  (this is where TCP errors actually surface)
# ---------------------------------------------------------------------------

@contextmanager
def get_connection(connection_string: Optional[str] = None) -> Generator[Connection, None, None]:
    """
    Yield a SQLAlchemy Connection from the engine pool.

    Raises a user-friendly ConnectionError (with Supabase troubleshooting
    steps) if the database is unreachable.

    Usage::

        with get_connection(conn_str) as conn:
            rows = conn.execute(text("SELECT * FROM employees")).fetchall()
    """
    try:
        engine = get_engine(connection_string)
        with engine.connect() as conn:
            yield conn
    except OperationalError as exc:
        raw_detail = str(exc.orig or exc)

        # Build a clear, actionable error message
        if "could not translate host name" in raw_detail or "Name or service not known" in raw_detail:
            hint = (
                "DNS resolution failed — the database hostname could not be found.\n"
                "Most likely cause: you are using the DIRECT connection URL which "
                "requires IPv6, or your Supabase project is paused."
            )
        elif "Connection refused" in raw_detail:
            hint = "Connection refused — the database port is not reachable."
        elif "password authentication failed" in raw_detail:
            hint = "Password authentication failed — check your database password."
        elif "SSL" in raw_detail:
            hint = "SSL error — try adding ?sslmode=require to your connection string."
        else:
            hint = "Could not establish a database connection."

        raise ConnectionError(
            f"{hint}\n{_SUPABASE_HELP}\nOriginal error: {raw_detail}"
        ) from exc


# ---------------------------------------------------------------------------
# Verification (optional — called explicitly after schema discovery)
# ---------------------------------------------------------------------------

def verify_connection(connection_string: Optional[str] = None) -> bool:
    """
    Attempt a lightweight SELECT 1 and return True on success.
    Returns False (and logs) on failure — does NOT raise.
    Useful for health-check endpoints.
    """
    try:
        with get_connection(connection_string) as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("DB connection check failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def dispose_engine(connection_string: str) -> None:
    """
    Remove and dispose the cached engine, releasing all pooled connections.
    """
    resolved = _resolve_connection_string(connection_string)
    engine = _ENGINE_CACHE.pop(resolved, None)
    if engine:
        engine.dispose()
        logger.info("Engine disposed for host: %s", _safe_host(resolved))

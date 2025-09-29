from __future__ import annotations

from contextlib import contextmanager
from typing import Dict
import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine import make_url

from backend.api.config import get_settings

_ENGINE_CACHE: Dict[str, Engine] = {}


def get_engine(connection_string: str | None = None) -> Engine:
    settings = get_settings()
    conn_str = connection_string or settings.database.connection_string
    if not conn_str:
        raise ValueError("Database connection string is required.")

    # Normalize Postgres driver: prefer psycopg v3 if no explicit driver provided
    # This avoids 'No module named psycopg2' on Python 3.13+ when users pass
    # a bare 'postgresql://...' URL which otherwise defaults to psycopg2.
    try:
        url = make_url(conn_str)
        backend = url.get_backend_name()
        driver = url.get_driver_name() or ""
        if backend in {"postgresql", "postgres"} and driver in {"", "psycopg2", "psycopg2cffi"}:
            # Upgrade to psycopg v3 driver implicitly for compatibility
            conn_str = str(url.set(drivername="postgresql+psycopg"))
            logging.getLogger(__name__).info(
                "Upgraded Postgres URL to psycopg v3 driver for compatibility: %s",
                conn_str.split("@", 1)[0] + "@…",  # avoid logging credentials
            )
    except Exception:  # noqa: BLE001
        # If URL parsing fails, fall back to original string
        pass

    if conn_str not in _ENGINE_CACHE:
        _ENGINE_CACHE[conn_str] = create_engine(
            conn_str,
            pool_pre_ping=True,
            pool_size=settings.database.pool_size,
            pool_timeout=settings.database.pool_timeout,
        )
    return _ENGINE_CACHE[conn_str]


@contextmanager
def get_connection(connection_string: str | None = None):
    engine = get_engine(connection_string)
    with engine.connect() as conn:
        yield conn

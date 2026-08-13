from __future__ import annotations

import logging
import threading
from typing import Dict, Optional

from backend.api.services.query_engine import QueryEngine

logger = logging.getLogger(__name__)


class EngineRegistry:
    """Thread-safe registry of QueryEngine instances keyed by connection string."""

    def __init__(self) -> None:
        self._engines: Dict[str, QueryEngine] = {}
        self._lock = threading.Lock()

    def get_engine(self, connection_string: str) -> QueryEngine:
        """Return a cached QueryEngine, creating one if it doesn't exist yet."""
        with self._lock:
            if connection_string not in self._engines:
                logger.info("[EngineRegistry] Initialising new QueryEngine for connection.")
                self._engines[connection_string] = QueryEngine(connection_string)
            return self._engines[connection_string]

    def drop_engine(self, connection_string: str) -> None:
        """Remove a QueryEngine from the registry and release its DB pool."""
        with self._lock:
            engine = self._engines.pop(connection_string, None)
            if engine:
                try:
                    from backend.api.database import dispose_engine
                    dispose_engine(connection_string)
                except Exception:  # noqa: BLE001
                    pass
                logger.info("[EngineRegistry] Engine dropped for connection.")

    def clear(self) -> None:
        """Remove all cached engines."""
        with self._lock:
            for conn_str in list(self._engines.keys()):
                self.drop_engine(conn_str)
            self._engines.clear()

    def active_connections(self) -> int:
        with self._lock:
            return len(self._engines)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_REGISTRY: Optional[EngineRegistry] = None
_REGISTRY_LOCK = threading.Lock()


def get_registry() -> EngineRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        with _REGISTRY_LOCK:
            if _REGISTRY is None:
                _REGISTRY = EngineRegistry()
    return _REGISTRY

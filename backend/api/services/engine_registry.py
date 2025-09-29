from __future__ import annotations

import threading
from typing import Dict

from backend.api.services.query_engine import QueryEngine


class EngineRegistry:
    """Thread-safe registry of query engine instances per connection string."""

    def __init__(self) -> None:
        self._engines: Dict[str, QueryEngine] = {}
        self._lock = threading.Lock()

    def get_engine(self, connection_string: str) -> QueryEngine:
        with self._lock:
            if connection_string not in self._engines:
                self._engines[connection_string] = QueryEngine(connection_string)
            return self._engines[connection_string]

    def drop_engine(self, connection_string: str) -> None:
        with self._lock:
            self._engines.pop(connection_string, None)

    def clear(self) -> None:
        with self._lock:
            self._engines.clear()


def get_registry() -> EngineRegistry:
    global _REGISTRY
    try:
        return _REGISTRY
    except NameError:
        _REGISTRY = EngineRegistry()
        return _REGISTRY

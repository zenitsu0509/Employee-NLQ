from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional, Tuple


class TTLCache:
    """Thread-safe TTL cache with optional size limit."""

    def __init__(self, ttl_seconds: int = 300, max_size: int = 1000) -> None:
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._data: Dict[str, Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._data:
                return None
            expires_at, value = self._data[key]
            if expires_at < time.time():
                del self._data[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._data) >= self._max_size:
                self._evict()
            self._data[key] = (time.time() + self._ttl, value)

    def _evict(self) -> None:
        if not self._data:
            return
        oldest_key = min(self._data.items(), key=lambda item: item[1][0])[0]
        del self._data[oldest_key]

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

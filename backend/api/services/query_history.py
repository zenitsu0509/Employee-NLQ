from __future__ import annotations

import threading
from collections import deque
from typing import Deque, Dict, List


class QueryHistory:
    """Thread-safe bounded history for executed queries."""

    def __init__(self, capacity: int = 100) -> None:
        self._capacity = capacity
        self._history: Deque[Dict[str, object]] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def add(self, record: Dict[str, object]) -> None:
        with self._lock:
            self._history.appendleft(record)

    def list(self) -> List[Dict[str, object]]:
        with self._lock:
            return list(self._history)

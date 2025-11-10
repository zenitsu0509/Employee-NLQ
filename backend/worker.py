from __future__ import annotations

"""RQ worker entrypoint.

Run with:
    python -m rq worker -u <redis_url> <queue_name>

Or simply:
    python backend/worker.py
which uses config.yml for redis_url and queue name.
"""

import os
import sys
from rq import Worker, Queue, Connection
from redis import Redis

# Allow running this script from either project root (preferred) or backend/ dir.
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from backend.api.config import get_settings
except ModuleNotFoundError:
    # Fallback: user executed inside backend/ and package resolution failed.
    print(
        "[worker] Could not import 'backend.api.config'. Ensure you run this via:\n"
        "  python -m backend.worker   (from project root)\n"
        "or adjust PYTHONPATH to include the project root."
    )
    raise


def main() -> int:
    settings = get_settings()
    if not settings.queue.enabled:
        print("Queue is disabled in config.yml (queue.enabled=false)")
        return 1
    redis_url = settings.queue.redis_url
    queue_name = settings.queue.queue_name
    conn = Redis.from_url(redis_url)
    with Connection(conn):
        w = Worker([Queue(queue_name)])
        print(f"[worker] Starting RQ worker for queue '{queue_name}' at {redis_url}")
        w.work()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Optional
import json

try:  # optional dependency
    from redis import Redis  # type: ignore
except Exception:  # pragma: no cover
    Redis = None  # type: ignore


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class JobProgress:
    job_id: str
    status: JobStatus = JobStatus.PENDING
    processed: int = 0
    total: int = 0
    message: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)


class JobTracker:
    """In-memory tracker for ingestion and processing jobs."""

    def __init__(self) -> None:
        self._jobs: Dict[str, JobProgress] = {}
        self._lock = threading.Lock()

    def create_job(self, total: int = 0, metadata: Optional[Dict[str, str]] = None) -> JobProgress:
        job = JobProgress(job_id=str(uuid.uuid4()), total=total, metadata=metadata or {})
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def update_job(self, job_id: str, *, processed: Optional[int] = None, total: Optional[int] = None,
                   status: Optional[JobStatus] = None, message: Optional[str] = None) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if processed is not None:
                job.processed = processed
            if total is not None:
                job.total = total
            if status is not None:
                job.status = status
            if message is not None:
                job.message = message

    def get_job(self, job_id: str) -> Optional[JobProgress]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> Dict[str, JobProgress]:
        with self._lock:
            return dict(self._jobs)


class RedisJobTracker:
    """Redis-backed job tracker for multi-process visibility."""

    def __init__(self, conn: "Redis", namespace: str = "jobs") -> None:  # type: ignore[name-defined]
        if conn is None:
            raise RuntimeError("Redis connection is required for RedisJobTracker")
        self._r = conn
        self._ns = namespace
        self._index_key = f"{self._ns}:index"

    def _job_key(self, job_id: str) -> str:
        return f"{self._ns}:{job_id}"

    def create_job(self, total: int = 0, metadata: Optional[Dict[str, str]] = None) -> JobProgress:
        job = JobProgress(job_id=str(uuid.uuid4()), total=total, metadata=metadata or {})
        self._r.sadd(self._index_key, job.job_id)
        self._r.set(self._job_key(job.job_id), json.dumps(asdict(job)))
        return job

    def update_job(
        self,
        job_id: str,
        *,
        processed: Optional[int] = None,
        total: Optional[int] = None,
        status: Optional[JobStatus] = None,
        message: Optional[str] = None,
    ) -> None:
        data = self._r.get(self._job_key(job_id))
        if not data:
            return
        raw = json.loads(data)
        if processed is not None:
            raw["processed"] = processed
        if total is not None:
            raw["total"] = total
        if status is not None:
            raw["status"] = status.value if isinstance(status, JobStatus) else str(status)
        if message is not None:
            raw["message"] = message
        self._r.set(self._job_key(job_id), json.dumps(raw))

    def get_job(self, job_id: str) -> Optional[JobProgress]:
        data = self._r.get(self._job_key(job_id))
        if not data:
            return None
        raw = json.loads(data)
        return JobProgress(
            job_id=raw["job_id"],
            status=JobStatus(raw.get("status", JobStatus.PENDING)),
            processed=int(raw.get("processed", 0)),
            total=int(raw.get("total", 0)),
            message=raw.get("message"),
            metadata=raw.get("metadata", {}),
        )

    def list_jobs(self) -> Dict[str, JobProgress]:
        ids = [i.decode("utf-8") if isinstance(i, (bytes, bytearray)) else i for i in self._r.smembers(self._index_key)]
        out: Dict[str, JobProgress] = {}
        for jid in ids:
            job = self.get_job(jid)
            if job:
                out[jid] = job
        return out

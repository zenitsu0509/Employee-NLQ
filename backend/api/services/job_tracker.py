from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


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

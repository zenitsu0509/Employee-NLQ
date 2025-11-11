from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status
from backend.api.config import get_settings

try:
    from rq import Queue
    from redis import Redis
except Exception:  # pragma: no cover - optional at dev time
    Queue = None  # type: ignore
    Redis = None  # type: ignore

from backend.api.models.requests import DatabaseConnectionRequest
from backend.api.models.responses import DocumentIngestionResponse
from backend.api.services.engine_registry import get_registry
from backend.api.services.job_tracker import JobStatus, JobTracker, RedisJobTracker
from backend.api.database import get_engine as get_sqlalchemy_engine
from backend.api.services.tabular_importer import import_file_to_db, ImportOptions

# Load settings before any conditional initialization that depends on them.
_settings = get_settings()
router = APIRouter(prefix="/ingest", tags=["ingestion"])

# Initialize a job tracker (Redis-backed if enabled & available, else in-memory)
if _settings.queue.enabled and Redis is not None:
    try:
        _redis_conn = Redis.from_url(_settings.queue.redis_url)
        job_tracker = RedisJobTracker(_redis_conn)
        print(f"[ingestion] Using RedisJobTracker at {_settings.queue.redis_url}")
    except Exception as exc:  # noqa: BLE001
        print(f"[ingestion] Failed to init RedisJobTracker, fallback to in-memory: {exc}")
        job_tracker = JobTracker()
else:
    job_tracker = JobTracker()

# Initialize Redis queue if enabled
_queue = None
if _settings.queue.enabled and Queue and Redis:
    try:
        _queue = Queue(
            _settings.queue.queue_name,
            connection=Redis.from_url(_settings.queue.redis_url),
        )
        print(
            f"[ingestion] Using Redis queue '{_settings.queue.queue_name}' at {_settings.queue.redis_url}"
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[ingestion] Failed to connect to Redis queue: {exc}")


@router.post("/database")
async def connect_database(payload: DatabaseConnectionRequest) -> dict:
    registry = get_registry()
    try:
        engine = registry.get_engine(payload.connection_string)
        schema = engine.refresh_schema()
        return {
            "message": "Database connected and schema discovered",
            "schema": schema,
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/documents", response_model=DocumentIngestionResponse)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    connection_string: str = Form(...),
) -> DocumentIngestionResponse:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files uploaded")

    registry = get_registry()
    try:
        registry.get_engine(connection_string)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    job = job_tracker.create_job(total=len(files), metadata={"connection_string": connection_string})
    temp_paths = []
    for upload in files:
        contents = await upload.read()
        if not upload.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file missing name")
        suffix = Path(upload.filename).suffix or ".dat"
        with NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp.write(contents)
            temp_paths.append(temp.name)

    if _queue is not None:
        _queue.enqueue(_process_documents_job, connection_string, temp_paths, job.job_id)
    else:
        background_tasks.add_task(_process_documents_job, connection_string, temp_paths, job.job_id)

    return DocumentIngestionResponse(
        job_id=job.job_id,
        status=job.status.value,
        processed=job.processed,
        total_files=job.total,
    )


@router.get("/jobs")
async def list_jobs() -> dict:
    """List all current ingestion jobs and their progress.

    Useful to discover the correct job_id to poll with /ingest/status/{job_id}.
    """
    jobs = job_tracker.list_jobs()
    return {
        "jobs": [
            {
                "job_id": job.job_id,
                "status": job.status.value,
                "processed": job.processed,
                "total": job.total,
                "message": job.message,
                "metadata": job.metadata,
            }
            for job in jobs.values()
        ]
    }


@router.get("/status/{job_id}")
async def get_status(job_id: str) -> dict:
    job = job_tracker.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "processed": job.processed,
        "total": job.total,
        "message": job.message,
        "metadata": job.metadata,
    }


def _process_documents_job(connection_string: str, temp_paths: List[str], job_id: str) -> None:
    registry = get_registry()
    job = job_tracker.get_job(job_id)
    try:
        engine = registry.get_engine(connection_string)
        engine.document_processor.process_documents((Path(path) for path in temp_paths), job)
    except Exception as exc:  # noqa: BLE001
        if job:
            job.status = JobStatus.FAILED
            job.message = str(exc)
    finally:
        for path in temp_paths:
            try:
                os.unlink(path)
            except FileNotFoundError:
                continue


@router.post("/tabular")
async def upload_tabular(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    connection_string: str = Form(...),
    if_exists: str = Form("append"),  # 'fail' | 'replace' | 'append'
    table_name: str | None = Form(None),
    delimiter: str | None = Form(None),
    sheet_name: str | None = Form(None),
) -> dict:
    """Upload CSV/XLSX and load into the target database (e.g., Neon/Supabase).

    - Infers table name from filename if not provided (sanitized)
    - Supports large CSV via chunked insert
    - if_exists: append (default), replace, or fail
    """
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files uploaded")

    # Validate access to the engine first
    registry = get_registry()
    try:
        registry.get_engine(connection_string)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    job = job_tracker.create_job(total=len(files), metadata={
        "connection_string": connection_string,
        "mode": "tabular",
        "if_exists": if_exists,
    })

    temp_paths: List[str] = []
    for upload in files:
        contents = await upload.read()
        if not upload.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file missing name")
        suffix = Path(upload.filename).suffix or ".dat"
        with NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp.write(contents)
            temp_paths.append(temp.name)

    if _queue is not None:
        _queue.enqueue(
            _process_tabular_job,
            connection_string,
            temp_paths,
            job.job_id,
            if_exists,
            table_name,
            delimiter,
            sheet_name,
        )
    else:
        background_tasks.add_task(
            _process_tabular_job,
            connection_string,
            temp_paths,
            job.job_id,
            if_exists,
            table_name,
            delimiter,
            sheet_name,
        )

    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "processed": job.processed,
        "total_files": job.total,
    }


def _process_tabular_job(
    connection_string: str,
    temp_paths: List[str],
    job_id: str,
    if_exists: str = "append",
    table_name: str | None = None,
    delimiter: str | None = None,
    sheet_name: str | None = None,
) -> None:
    job = job_tracker.get_job(job_id)
    try:
        engine = get_sqlalchemy_engine(connection_string)
        options = ImportOptions(
            table_name=table_name,
            if_exists=if_exists,
            delimiter=delimiter,
            sheet_name=sheet_name,
        )
        for idx, path in enumerate(temp_paths, start=1):
            used_table = import_file_to_db(engine, Path(path), options)
            if job:
                job.processed = idx
                job.message = f"Imported {Path(path).name} into {used_table}"
        if job:
            job.status = JobStatus.COMPLETED
            job.message = f"Imported {len(temp_paths)} file(s)"
    except Exception as exc:  # noqa: BLE001
        if job:
            job.status = JobStatus.FAILED
            job.message = str(exc)
    finally:
        for path in temp_paths:
            try:
                os.unlink(path)
            except FileNotFoundError:
                continue

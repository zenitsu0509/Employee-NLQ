from __future__ import annotations

import logging
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status

from backend.api.models.requests import DatabaseConnectionRequest
from backend.api.models.responses import DocumentIngestionResponse
from backend.api.services.engine_registry import get_registry
from backend.api.services.job_tracker import JobStatus, JobTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingestion"])
job_tracker = JobTracker()


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

@router.post("/database")
async def connect_database(payload: DatabaseConnectionRequest) -> dict:
    """
    Connect to a database, run schema discovery, and cache the engine.

    Returns the discovered schema so the frontend can preview available tables.
    """
    registry = get_registry()
    try:
        engine = registry.get_engine(payload.connection_string)
        schema = engine.refresh_schema()
        table_names = [t["name"] for t in schema.get("tables", [])]
        return {
            "message": "Database connected and schema discovered",
            "tables_found": len(table_names),
            "tables": table_names,
            "schema": schema,
        }
    except ConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/database")
async def disconnect_database(connection_string: str) -> dict:
    """Drop the cached engine and release the connection pool for a given DB."""
    try:
        get_registry().drop_engine(connection_string)
        return {"message": "Database disconnected and connection pool released."}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Document ingestion
# ---------------------------------------------------------------------------

@router.post("/documents", response_model=DocumentIngestionResponse)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    connection_string: str = Form(...),
) -> DocumentIngestionResponse:
    """Upload one or more documents (PDF, DOCX, TXT) for vector ingestion."""
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files uploaded")

    registry = get_registry()
    try:
        registry.get_engine(connection_string)
    except ConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    job = job_tracker.create_job(total=len(files), metadata={"connection_string": connection_string})
    temp_paths: List[str] = []

    for upload in files:
        contents = await upload.read()
        if not upload.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is missing a filename",
            )
        suffix = Path(upload.filename).suffix or ".dat"
        with NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp.write(contents)
            temp_paths.append(temp.name)

    background_tasks.add_task(_process_documents_job, connection_string, temp_paths, job.job_id)

    return DocumentIngestionResponse(
        job_id=job.job_id,
        status=job.status.value,
        processed=job.processed,
        total_files=job.total,
    )


# ---------------------------------------------------------------------------
# Job status
# ---------------------------------------------------------------------------

@router.get("/jobs")
async def list_jobs() -> dict:
    """List all current ingestion jobs and their progress."""
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
    """Poll the status of an ongoing ingestion job."""
    job = job_tracker.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found")
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "processed": job.processed,
        "total": job.total,
        "message": job.message,
        "metadata": job.metadata,
    }


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

def _process_documents_job(connection_string: str, temp_paths: List[str], job_id: str) -> None:
    registry = get_registry()
    job = job_tracker.get_job(job_id)
    try:
        engine = registry.get_engine(connection_string)
        engine.document_processor.process_documents((Path(p) for p in temp_paths), job)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[Ingestion] Background job %s failed: %s", job_id, exc)
        if job:
            job.status = JobStatus.FAILED
            job.message = str(exc)
    finally:
        for path in temp_paths:
            try:
                os.unlink(path)
            except FileNotFoundError:
                continue

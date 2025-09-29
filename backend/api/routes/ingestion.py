from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import List

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status

from backend.api.models.requests import DatabaseConnectionRequest
from backend.api.models.responses import DocumentIngestionResponse
from backend.api.services.engine_registry import get_registry
from backend.api.services.job_tracker import JobStatus, JobTracker

router = APIRouter(prefix="/ingest", tags=["ingestion"])
job_tracker = JobTracker()


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

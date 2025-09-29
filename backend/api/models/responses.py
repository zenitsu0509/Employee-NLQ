from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class QueryResultResponse(BaseModel):
    query: str
    query_type: str
    results: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    sources: Optional[List[Dict[str, Any]]]


class SchemaResponse(BaseModel):
    tables: List[dict]
    relationships: List[dict]
    synonyms: dict


class DocumentIngestionResponse(BaseModel):
    job_id: str
    total_files: int
    status: str
    processed: int


class QueryHistoryResponse(BaseModel):
    history: List[dict]

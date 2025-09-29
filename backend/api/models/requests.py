from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DatabaseConnectionRequest(BaseModel):
    connection_string: str = Field(..., min_length=5)


class QueryRequest(BaseModel):
    query: str
    top_k: int = Field(default=10, ge=1, le=50)
    connection_string: Optional[str] = None

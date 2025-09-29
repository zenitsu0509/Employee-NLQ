from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class SchemaTable(BaseModel):
    name: str
    columns: List[str]
    sample_rows: Optional[List[Dict[str, Any]]] = None


class SchemaRelationship(BaseModel):
    from_table: str
    to_table: str
    via_columns: Dict[str, str]


class QueryResult(BaseModel):
    query: str
    query_type: str
    results: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    sources: Optional[List[Dict[str, Any]]] = None

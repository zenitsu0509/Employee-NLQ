from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import time 
import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import text

from backend.api.config import get_settings
from backend.api.database import get_connection
from backend.api.services.cache import TTLCache
from backend.api.services.document_processor import DocumentProcessor
from backend.api.services.job_tracker import JobProgress
from backend.api.services.query_classifier import QueryClassifier, QueryType
from backend.api.services.query_history import QueryHistory
from backend.api.services.schema_discovery import SchemaDiscovery
from backend.api.services.sql_generator import SQLGenerator
from backend.api.services.vector_store import VectorStore
from backend.api.services.groq_sql_generator import GroqSQLGenerator


@dataclass
class QueryResponse:
    query: str
    query_type: str
    results: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    sources: Optional[List[Dict[str, Any]]] = None


class QueryEngine:
    """Unified query engine handling structured and unstructured queries."""

    def __init__(self, connection_string: str) -> None:
        self._connection_string = connection_string
        self._settings = get_settings()
        self.schema_discovery = SchemaDiscovery()
        self.schema = self.schema_discovery.analyze_database(connection_string)
        self.sql_generator = GroqSQLGenerator(self.schema)
        self.classifier = QueryClassifier()
        self.cache = TTLCache(
            ttl_seconds=self._settings.cache.ttl_seconds,
            max_size=self._settings.cache.max_size,
        )
        self.history = QueryHistory()

        self._embedder = SentenceTransformer(self._settings.embeddings.model, device=self._settings.embeddings.device)
        self._vector_store = VectorStore(self._embedder.get_sentence_embedding_dimension())
        self.document_processor = DocumentProcessor(
            self._vector_store,
            model=self._embedder,
            batch_size=self._settings.embeddings.batch_size,
        )

    def ingest_documents(self, files: Iterable[str], job: JobProgress | None = None) -> Dict[str, Any]:
        paths = [file for file in files]
        processed = self.document_processor.process_documents((Path(file) for file in paths), job)
        return {
            "indexed": len(processed),
            "vector_store_size": self._vector_store.size(),
        }

    def process_query(self, user_query: str, top_k: int = 10) -> Dict[str, Any]:
        start_time = time.perf_counter()
        cached = self.cache.get(user_query)
        if cached:
            cached_response = cached.copy()
            cached_response["metrics"] = {**cached_response.get("metrics", {}), "cache_hit": True}
            return cached_response

        query_type = self.classifier.classify(user_query)
        results: List[Dict[str, Any]] = []
        sources: List[Dict[str, Any]] = []

        if query_type in {QueryType.SQL, QueryType.HYBRID}:
            sql_results = self._execute_sql_query(user_query)
            results.extend(sql_results)

        if query_type in {QueryType.DOCUMENT, QueryType.HYBRID}:
            doc_chunks = self._search_documents(user_query, top_k=top_k)
            sources.extend(doc_chunks)

        final_type = query_type
        if results and not sources:
            final_type = QueryType.SQL
        elif sources and not results:
            final_type = QueryType.DOCUMENT
        elif results and sources:
            final_type = QueryType.HYBRID

        response = QueryResponse(
            query=user_query,
            query_type=final_type.value,
            results=results,
            metrics={
                "response_ms": round((time.perf_counter() - start_time) * 1000, 2),
                "cache_hit": False,
                "doc_index_size": self._vector_store.size(),
            },
            sources=sources or None,
        )

        data = asdict(response)
        self.cache.set(user_query, data)
        self.history.add({"query": user_query, "type": final_type.value, "timestamp": time.time()})
        return data

    def get_history(self) -> List[Dict[str, Any]]:
        return self.history.list()

    def refresh_schema(self) -> Dict[str, Any]:
        self.schema = self.schema_discovery.analyze_database(self._connection_string)
        self.sql_generator = GroqSQLGenerator(self.schema)
        return self.schema

    def optimize_sql_query(self, sql: str) -> str:
        """Add LIMIT clause if missing to prevent large result sets (SELECT only)."""
        optimized = sql.strip()
        
        # Remove trailing semicolon if present
        if optimized.endswith(';'):
            optimized = optimized[:-1].strip()
        
        # Check if this is a data modification statement
        sql_upper = optimized.upper()
        is_dml = any(sql_upper.startswith(keyword) for keyword in ['UPDATE', 'INSERT', 'DELETE', 'CREATE', 'DROP', 'ALTER'])
        
        # Only add LIMIT for SELECT queries
        if not is_dml and "limit" not in optimized.lower():
            optimized = f"{optimized} LIMIT 100"
        
        return optimized

    def _convert_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert row values to JSON-serializable types."""
        new_row: Dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, Decimal):
                new_row[key] = float(value)
            elif isinstance(value, (date, datetime)):
                new_row[key] = value.isoformat()
            elif isinstance(value, (np.integer,)):
                new_row[key] = int(value)
            elif isinstance(value, (np.floating,)):
                new_row[key] = float(value)
            elif isinstance(value, (bytes, bytearray, memoryview)):
                new_row[key] = value.decode("utf-8", errors="replace")
            else:
                new_row[key] = value
        return new_row

    def _execute_sql_query(self, user_query: str) -> List[Dict[str, Any]]:
        mapping = self.schema_discovery.map_natural_language_to_schema(user_query, self.schema)
        table = mapping.get("likely_tables", [None])[0]
        print(f"[QueryEngine] Likely table for query '{user_query}': {table}")
        
        sql_plan = self.sql_generator.generate(user_query, table=table)
        if not sql_plan:
            print(f"[QueryEngine] No SQL plan generated for query: {user_query}")
            return []

        print(f"[QueryEngine] Executing SQL: {sql_plan.sql}")
        sql = self.optimize_sql_query(sql_plan.sql)
        
        with get_connection(self._connection_string) as conn:
            result = conn.execute(text(sql), sql_plan.params)
            
            # For DML operations (UPDATE, INSERT, DELETE), return affected row count
            if result.rowcount >= 0 and not result.returns_rows:
                conn.commit()
                return [{"affected_rows": result.rowcount, "status": "success"}]
            
            # For SELECT queries, return the actual rows
            rows = [self._convert_row(dict(row._mapping)) for row in result]
        return rows

    def _search_documents(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        if self._vector_store.size() == 0:
            return []
        embedding = self._embedder.encode([query])
        chunks = self._vector_store.search(np.array(embedding), top_k=top_k)
        return [
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "content": chunk.content,
                "metadata": chunk.metadata,
            }
            for chunk in chunks
        ]

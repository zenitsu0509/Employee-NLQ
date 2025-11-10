from __future__ import annotations

"""Persistent PgVector-backed document chunk store.

Requires the 'pgvector' extension installed in the target Postgres database.
The table is created lazily if missing.
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass
class PersistentChunk:
    chunk_id: str
    document_id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Sequence[float]


class PgVectorStore:
    def __init__(self, engine: Engine, table_name: str, dimension: int) -> None:
        self._engine = engine
        self._table = table_name
        self._dimension = dimension
        self._ensure_schema()

    @property
    def dimension(self) -> int:
        return self._dimension

    def _ensure_schema(self) -> None:
        ddl = f"""
        CREATE TABLE IF NOT EXISTS {self._table} (
            id UUID PRIMARY KEY,
            document_id TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata JSONB,
            embedding vector({self._dimension})
        );
        """
        with self._engine.begin() as conn:
            conn.execute(text(ddl))

    def clear(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {self._table}"))

    def size(self) -> int:
        with self._engine.begin() as conn:
            row = conn.execute(text(f"SELECT COUNT(*) AS c FROM {self._table}")).first()
            return int(row.c) if row else 0

    def add(self, embeddings, chunks: List[PersistentChunk]) -> None:
        if embeddings.shape[1] != self._dimension:
            raise ValueError("Embedding dimension mismatch")
        rows = []
        for emb, chunk in zip(embeddings, chunks):
            rows.append({
                "id": str(uuid.uuid4()),
                "document_id": chunk.document_id,
                "content": chunk.content,
                "metadata": json.dumps(chunk.metadata),
                "embedding": list(map(float, emb.tolist())),
            })
        # Use unnest for batch insert; fallback to simple loop for clarity
        insert_sql = f"""
        INSERT INTO {self._table} (id, document_id, content, metadata, embedding)
        VALUES (:id, :document_id, :content, CAST(:metadata AS JSONB), :embedding)
        """
        with self._engine.begin() as conn:
            for r in rows:
                conn.execute(text(insert_sql), r)

    def search(self, embedding, top_k: int = 5) -> List[PersistentChunk]:
        if embedding.shape[-1] != self._dimension:
            raise ValueError("Embedding dimension mismatch")
        # Use the `<=>` distance operator (Euclidean) or `<#>` for cosine if normalized
        sql = text(f"""
            SELECT id, document_id, content, metadata, embedding
            FROM {self._table}
            ORDER BY embedding <-> :query_embedding
            LIMIT :limit
        """)
        query_emb = list(map(float, embedding[0].tolist()))
        results = []
        with self._engine.begin() as conn:
            for row in conn.execute(sql, {"query_embedding": query_emb, "limit": top_k}):
                results.append(
                    PersistentChunk(
                        chunk_id=str(row.id),
                        document_id=row.document_id,
                        content=row.content,
                        metadata=row.metadata if isinstance(row.metadata, dict) else {},
                        embedding=row.embedding,
                    )
                )
        return results
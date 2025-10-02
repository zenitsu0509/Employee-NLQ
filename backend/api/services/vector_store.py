from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, List

import faiss
import numpy as np


@dataclass
class DocumentChunk:
    chunk_id: str
    document_id: str
    content: str
    metadata: Dict[str, Any]


class VectorStore:
    """Thread-safe FAISS vector store for document chunks."""

    def __init__(self, embedding_dimension: int) -> None:
        self._dimension = embedding_dimension
        self._index = faiss.IndexFlatL2(embedding_dimension)
        self._chunks: List[DocumentChunk] = []
        self._lock = threading.Lock()

    @property
    def dimension(self) -> int:
        return self._dimension

    def add(self, embeddings: np.ndarray, chunks: List[DocumentChunk]) -> None:
        if embeddings.shape[1] != self._dimension:
            raise ValueError("Embedding dimension mismatch")
        with self._lock:
            self._index.add(embeddings.astype("float32"))
            self._chunks.extend(chunks)

    def search(self, embedding: np.ndarray, top_k: int = 5) -> List[DocumentChunk]:
        if embedding.shape[-1] != self._dimension:
            raise ValueError("Embedding dimension mismatch")
        if len(self._chunks) == 0:
            return []
        with self._lock:
            distances, indices = self._index.search(embedding.astype("float32"), top_k)
            # Filter out invalid indices: FAISS returns -1 when not enough results
            return [self._chunks[idx] for idx in indices[0] if 0 <= idx < len(self._chunks)]

    def clear(self) -> None:
        with self._lock:
            self._index.reset()
            self._chunks.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._chunks)

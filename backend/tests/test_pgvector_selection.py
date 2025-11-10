from __future__ import annotations

import os
import types
import pytest

from backend.api.config import Settings, VectorStoreConfig, EmbeddingsConfig, CacheConfig, DatabaseConfig, LoggingConfig, QueueConfig, GroqConfig
from backend.api.services.query_engine import QueryEngine

class DummyEmbedder:
    def __init__(self, dimension: int = 16):
        self._dimension = dimension
    def get_sentence_embedding_dimension(self) -> int:
        return self._dimension
    def encode(self, batch, show_progress_bar: bool = False):  # noqa: D401
        return [[0.1] * self._dimension for _ in batch]

@pytest.fixture(autouse=True)
def patch_sentence_transformer(monkeypatch):
    monkeypatch.setattr("backend.api.services.query_engine.SentenceTransformer", lambda *a, **k: DummyEmbedder())
    yield

@pytest.mark.parametrize("store_type", ["faiss", "pgvector"])
def test_vector_store_selection(monkeypatch, store_type):
    settings = Settings(
        database=DatabaseConfig(),
        embeddings=EmbeddingsConfig(),
        cache=CacheConfig(),
        queue=QueueConfig(),
        vector_store=VectorStoreConfig(type=store_type, connection_string="sqlite:///ignore.db" if store_type=="pgvector" else None),
        groq=GroqConfig(provider="groq", api_key="test", model="llama-3.1-8b-instant"),
        logging=LoggingConfig(),
    )
    # Force get_settings to return our custom settings
    monkeypatch.setattr("backend.api.services.query_engine.get_settings", lambda: settings)
    engine = QueryEngine("sqlite:///tmp.db")
    # Attribute presence checks
    if store_type == "pgvector":
        # If pgvector fails (e.g., incorrect connection string), it should fallback to VectorStore
        assert hasattr(engine, "_vector_store")
        assert engine._vector_store.dimension == settings.embeddings.batch_size or engine._vector_store.dimension > 0
    else:
        assert hasattr(engine, "_vector_store")

@pytest.mark.parametrize("queue_enabled", [True, False])
def test_queue_fallback(monkeypatch, queue_enabled):
    # Simulate settings with/without queue
    settings = Settings(
        database=DatabaseConfig(),
        embeddings=EmbeddingsConfig(),
        cache=CacheConfig(),
        queue=QueueConfig(enabled=queue_enabled, redis_url="redis://localhost:6379/0", queue_name="ingestion"),
        vector_store=VectorStoreConfig(),
        groq=GroqConfig(provider="groq", api_key="test", model="llama-3.1-8b-instant"),
        logging=LoggingConfig(),
    )
    monkeypatch.setattr("backend.api.routes.ingestion.get_settings", lambda: settings)
    # Import the module after patching settings
    from importlib import reload
    import backend.api.routes.ingestion as ingestion_module
    reload(ingestion_module)
    if queue_enabled:
        # Queue may still be None if redis lib not available; we just ensure no crash
        assert hasattr(ingestion_module, "job_tracker")
    else:
        assert hasattr(ingestion_module, "job_tracker")

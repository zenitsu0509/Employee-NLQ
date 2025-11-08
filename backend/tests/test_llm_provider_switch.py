from __future__ import annotations

import types
import pytest

from backend.api.services.groq_sql_generator import GroqSQLGenerator
from backend.api.config import Settings, GroqConfig, CacheConfig, EmbeddingsConfig, DatabaseConfig, LoggingConfig


class DummyOpenAIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, messages, model: str, temperature: float, max_tokens: int):  # noqa: D401
        # Return a deterministic minimal SQL for testing
        class Choice:  # noqa: D401
            def __init__(self):
                self.message = types.SimpleNamespace(content="SELECT 1;")

        return types.SimpleNamespace(choices=[Choice()])


class DummyGroqClient(DummyOpenAIClient):
    pass


@pytest.mark.parametrize("provider", ["openai", "groq"])
def test_provider_switch(monkeypatch, provider):
    # Build settings with chosen provider
    settings = Settings(
        database=DatabaseConfig(),
        embeddings=EmbeddingsConfig(),
        cache=CacheConfig(),
        groq=GroqConfig(provider=provider, api_key="test-key", model="gpt-oss-120b" if provider == "openai" else "llama-3.1-8b-instant"),
        logging=LoggingConfig(),
    )

    # Patch get_settings used inside GroqSQLGenerator
    monkeypatch.setattr("backend.api.services.groq_sql_generator.get_settings", lambda: settings)

    # Patch provider clients
    if provider == "openai":
        monkeypatch.setattr("backend.api.services.groq_sql_generator.OpenAI", lambda api_key: DummyOpenAIClient(api_key))
    else:
        monkeypatch.setattr("backend.api.services.groq_sql_generator.Groq", lambda api_key: DummyGroqClient(api_key))

    generator = GroqSQLGenerator(schema={"tables": []})
    sql_query = generator.generate("return one")
    assert sql_query is not None
    assert "SELECT" in sql_query.sql.upper()
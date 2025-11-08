from __future__ import annotations

import os
from functools import lru_cache
import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    connection_string: Optional[str] = Field(default=None)
    pool_size: int = Field(default=10, ge=1)
    pool_timeout: int = Field(default=30, ge=1)


class EmbeddingsConfig(BaseModel):
    model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    batch_size: int = Field(default=32, ge=1)
    device: str = Field(default="cpu")


class CacheConfig(BaseModel):
    ttl_seconds: int = Field(default=300, ge=1)
    max_size: int = Field(default=1000, ge=1)
    backend: str = Field(default="memory")


class GroqConfig(BaseModel):
    # Provider can be 'groq' (default) or 'openai'.
    provider: str = Field(default="groq")
    api_key: str
    # Default to a currently available Groq Llama 3.1 instant model.
    # Note: Keep the hyphen after 'llama' (e.g., 'llama-3.1-8b-instant').
    model: str = Field(default="llama-3.1-8b-instant")


class LoggingConfig(BaseModel):
    level: str = Field(default="INFO")
    retention_days: int = Field(default=7, ge=1)


class Settings(BaseModel):
    database: DatabaseConfig = DatabaseConfig()
    embeddings: EmbeddingsConfig = EmbeddingsConfig()
    cache: CacheConfig = CacheConfig()
    groq: Optional[GroqConfig] = None
    logging: LoggingConfig = LoggingConfig()


def _load_yaml_config(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    # Interpolate environment variables like ${VAR}
    pattern = re.compile(r"\$\{([^}]+)\}")

    def interpolate(value):
        if isinstance(value, str):
            def repl(match):
                var = match.group(1)
                return os.getenv(var, match.group(0))
            return pattern.sub(repl, value)
        return value

    def walk(obj):
        if isinstance(obj, dict):
            return {k: walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [walk(v) for v in obj]
        return interpolate(obj)

    return walk(raw)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    config_path = Path(os.getenv("CONFIG_PATH", Path.cwd() / "config.yml"))
    raw = _load_yaml_config(config_path)
    settings = Settings.model_validate(raw)
    # Simple runtime validation / guidance for common Groq model typos
    if settings.groq and settings.groq.model and settings.groq.model.startswith("llama3"):
        # User likely forgot the hyphen after 'llama'
        print(
            f"[config] WARNING: Groq model '{settings.groq.model}' looks malformed. Did you mean 'llama-3.1-8b-instant' or another hyphenated form?"
        )
    return settings


def reload_settings() -> Settings:
    """Invalidate cache and reload settings, useful after editing config.yml."""
    get_settings.cache_clear()  # type: ignore[attr-defined]
    return get_settings()

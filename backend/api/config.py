from __future__ import annotations

import os
from functools import lru_cache
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
    api_key: str
    model: str = "llama3-8b-8192"


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
        return yaml.safe_load(handle) or {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    config_path = Path(os.getenv("CONFIG_PATH", Path.cwd() / "config.yml"))
    raw = _load_yaml_config(config_path)
    return Settings.model_validate(raw)

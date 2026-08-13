from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


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
    model: str = "openai/gpt-oss-120b"


class LoggingConfig(BaseModel):
    level: str = Field(default="INFO")
    retention_days: int = Field(default=7, ge=1)


class Settings(BaseModel):
    database: DatabaseConfig = DatabaseConfig()
    embeddings: EmbeddingsConfig = EmbeddingsConfig()
    cache: CacheConfig = CacheConfig()
    groq: Optional[GroqConfig] = None
    logging: LoggingConfig = LoggingConfig()


def _expand_env_vars(val: Any) -> Any:
    """Recursively expand ${VAR} or $VAR in strings, dicts, and lists."""
    if isinstance(val, str):
        # Match ${VAR} or ${VAR:default}
        def repl(match: re.Match[str]) -> str:
            var_expr = match.group(1)
            if ":" in var_expr:
                name, default = var_expr.split(":", 1)
                return os.getenv(name, default)
            return os.getenv(var_expr, "")
        return re.sub(r"\$\{([^}]+)\}", repl, val)
    elif isinstance(val, dict):
        return {k: _expand_env_vars(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [_expand_env_vars(item) for item in val]
    return val


def _load_yaml_config(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    data = _expand_env_vars(data)
    
    # Fallback to direct environment variables if not present
    if "groq" in data and isinstance(data["groq"], dict):
        if not data["groq"].get("api_key") or data["groq"].get("api_key") == "${GROQ_API_KEY}":
            data["groq"]["api_key"] = os.getenv("GROQ_API_KEY", "")
    elif os.getenv("GROQ_API_KEY"):
        data["groq"] = {
            "api_key": os.getenv("GROQ_API_KEY", ""),
            "model": os.getenv("GROQ_MODEL", "llama3-70b-8192")
        }
        
    if "database" in data and isinstance(data["database"], dict):
        if not data["database"].get("connection_string") or data["database"].get("connection_string") == "${DATABASE_URL}":
            data["database"]["connection_string"] = os.getenv("DATABASE_URL", None)

    return data


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    config_path = Path(os.getenv("CONFIG_PATH", Path.cwd() / "config.yml"))
    raw = _load_yaml_config(config_path)
    return Settings.model_validate(raw)

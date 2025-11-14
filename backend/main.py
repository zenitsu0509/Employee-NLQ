import os
import logging
import traceback
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from backend.api.routes import ingestion, query, schema
except Exception as import_exc:  # noqa: BLE001
    # Capture heavy import failures (e.g., missing native libs or OOM) to aid cloud debugging.
    print("[startup] ERROR importing routers:", import_exc)
    traceback.print_exc()
    raise

from backend.api.config import reload_settings, get_settings

app = FastAPI(title="NLP Query Engine", version="0.1.0")

# Emit diagnostic info early for container debugging
try:
    _settings = get_settings()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    logging.getLogger(__name__).info(
        "Startup diagnostics: provider=%s model=%s db_conn_set=%s vector_store=%s",
        getattr(_settings.groq, "provider", None) if _settings.groq else None,
        getattr(_settings.groq, "model", None) if _settings.groq else None,
        bool(_settings.database.connection_string),
        _settings.vector_store.type,
    )
except Exception as cfg_exc:  # noqa: BLE001
    print("[startup] ERROR loading settings:", cfg_exc)
    traceback.print_exc()
    # Do not suppress; failing fast clarifies root cause
    raise


# CORS: allow frontend dev origins (adjust via CORS_ORIGINS env if needed)
default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]

env_origins = os.environ.get("CORS_ORIGINS", "").strip()
allowed_origins = (
    [o.strip() for o in env_origins.split(",") if o.strip()] if env_origins else default_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion.router, prefix="/api")
app.include_router(query.router, prefix="/api")
app.include_router(schema.router, prefix="/api")


@app.get("/health", tags=["system"])
async def health_check() -> dict:
    """Simple health check endpoint."""
    return {"status": "ok"}


@app.post("/admin/reload-config", tags=["system"])
async def admin_reload_config() -> dict:
    """Reload config.yml and clear cached settings (no auth for dev)."""
    settings = reload_settings()
    prov = getattr(settings.groq, "provider", None) if settings.groq else None
    model = getattr(settings.groq, "model", None) if settings.groq else None
    return {"reloaded": True, "provider": prov, "model": model}


@app.get("/admin/llm-info", tags=["system"])
async def admin_llm_info() -> dict:
    settings = get_settings()
    prov = getattr(settings.groq, "provider", None) if settings.groq else None
    model = getattr(settings.groq, "model", None) if settings.groq else None
    has_key = bool(settings.groq and settings.groq.api_key)
    return {"provider": prov, "model": model, "api_key_present": has_key}

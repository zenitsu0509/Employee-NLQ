import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import ingestion, query, schema

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

app = FastAPI(
    title="Employee NLQ Engine",
    description="Natural Language Query engine for HR databases with LLM-powered SQL generation.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ────────────────────────────────────────────────────────────────────
_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]

_env_origins = os.environ.get("CORS_ORIGINS", "").strip()
allowed_origins = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else _default_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(ingestion.router, prefix="/api")
app.include_router(query.router,     prefix="/api")
app.include_router(schema.router,    prefix="/api")


# ─── System endpoints ────────────────────────────────────────────────────────
@app.get("/health", tags=["system"], summary="Health check")
async def health_check() -> dict:
    """
    Returns service health including live database connectivity status.
    """
    from backend.api.services.engine_registry import get_registry
    from backend.api.database import verify_connection
    from backend.api.config import get_settings

    registry = get_registry()
    settings = get_settings()

    # Try the default DB from config (if set)
    db_status = "unconfigured"
    if settings.database.connection_string:
        db_status = "ok" if verify_connection(settings.database.connection_string) else "unreachable"

    return {
        "status": "ok",
        "version": app.version,
        "database": db_status,
        "active_connections": registry.active_connections(),
    }


@app.get("/", tags=["system"], include_in_schema=False)
async def root() -> dict:
    return {"message": "Employee NLQ Engine is running. Visit /docs for the API reference."}

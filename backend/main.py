import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import ingestion, query, schema

app = FastAPI(title="NLP Query Engine", version="0.1.0")


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

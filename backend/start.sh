#!/usr/bin/env bash
set -euo pipefail

# Ensure working directory is /app
cd /app

# If a DATABASE_URL or VECTOR_DB_URL is present, run alembic migrations
if [[ -n "${DATABASE_URL:-}" || -n "${VECTOR_DB_URL:-}" ]]; then
  echo "[start] Running Alembic migrations..."
  alembic upgrade head || {
    echo "[start] Alembic migration failed (this may be okay if DB is not provisioned yet)." >&2
  }
else
  echo "[start] No DATABASE_URL/VECTOR_DB_URL set; skipping migrations."
fi

# Start FastAPI app
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000

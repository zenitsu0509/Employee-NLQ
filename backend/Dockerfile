# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for scientific stack and Postgres
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        curl \
        libsndfile1 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install first for better caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy backend source, alembic, and config
COPY backend /app/backend
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY config.yml /app/config.yml

# Expose FastAPI port
EXPOSE 8000

# Copy entrypoint script
COPY backend/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Default command runs DB migrations then starts the API
CMD ["/app/start.sh"]

# NLP Query Engine for Employee Data

This project delivers a full-stack AI-powered query system that can ingest employee databases and unstructured documents, automatically discover schemas, and serve natural language queries with production-ready optimizations.

## Project Overview

- **Backend**: FastAPI service providing ingestion, schema discovery, and query endpoints
- **Frontend**: React application for database configuration, document uploads, query interface, and analytics
- **Document Processing**: Multi-format ingestion with adaptive chunking and embedding generation
- **Query Engine**: Unified SQL and semantic retrieval with caching, optimization, and monitoring hooks

## Quick Start

### Prerequisites

- Python 3.11+ 
- Node.js 18+
- PostgreSQL (optional, SQLite works for testing)

### Backend Setup

1. **Create virtual environment and install dependencies:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r ../requirements.txt
```

2. **Run the FastAPI server:**
```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

3. **Test the API:**
```bash
curl http://localhost:8000/health
```

### Frontend Setup

1. **Install Node.js dependencies:**
```bash
cd frontend
npm install
```

2. **Start the development server:**
```bash
npm run dev
```

3. **Access the web interface:**
Open http://localhost:5173 in your browser

### Docker Setup (Alternative)

1. **Run with Docker Compose:**
```bash
docker-compose up --build
```

This starts:
- Backend API: http://localhost:8000
- Frontend UI: http://localhost:5173
- PostgreSQL: localhost:5432
- Redis: localhost:6379

## Usage Examples

### 1. Connect to Database

```bash
curl -X POST http://localhost:8000/api/ingest/database \
  -H "Content-Type: application/json" \
  -d '{"connection_string": "postgresql+psycopg://user:password@localhost:5432/employees"}'
```

### 2. Upload Documents

```bash
curl -X POST http://localhost:8000/api/ingest/documents \
  -F "files=@resume.pdf" \
  -F "files=@handbook.docx"
```

### 3. Query Your Data

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How many employees hired this year?", "top_k": 5}'
```

## Testing

Run the backend test suite:

```bash
cd backend
python -m pytest tests/ -v
```

## Configuration

Edit `config.yml` to customize:

- Database connection pooling
- Embedding model settings
- Cache configuration
- Logging levels

Notes:

- When using PostgreSQL with SQLAlchemy 2.x, prefer the psycopg v3 driver by specifying `postgresql+psycopg://...` in the connection string. This avoids requiring `psycopg2`.
- If running the backend inside Docker Compose, your connection string host should be the service name:
  - `postgresql+psycopg://user:password@postgres:5432/employees`
  If running the backend locally against Dockerized Postgres on your machine, use:
  - `postgresql+psycopg://user:password@localhost:5432/employees`

## Architecture

### Backend Structure

```text
backend/
├── api/
│   ├── routes/          # FastAPI endpoints
│   ├── services/        # Business logic
│   │   ├── schema_discovery.py    # Auto-discover DB schemas
│   │   ├── query_engine.py        # Unified query processing
│   │   ├── document_processor.py  # Document ingestion
│   │   └── vector_store.py        # Semantic search
│   └── models/          # Pydantic schemas
└── tests/               # Unit tests
```

### Frontend Structure

```text
frontend/src/
├── components/
│   ├── AppLayout.tsx           # Main layout
│   └── contexts/              # React contexts
├── App.tsx                    # Root component
└── main.tsx                   # Entry point
```

## Features

✅ **Schema Discovery**: Automatically detects table structures and relationships  
✅ **Natural Language Queries**: Converts English to SQL and semantic search  
✅ **Document Processing**: Handles PDFs, Word docs, CSVs with intelligent chunking  
✅ **Caching**: TTL-based response caching for performance  
✅ **Multi-format Results**: Returns structured data and document excerpts  
✅ **Query History**: Tracks and caches previous queries  

## Troubleshooting

- No module named 'psycopg2'
  - Cause: SQLAlchemy is attempting to use the old psycopg2 driver when your environment only has psycopg v3 installed (as specified in `requirements.txt`).
  - Fix: Use a connection string that explicitly selects psycopg v3: `postgresql+psycopg://user:password@host:5432/dbname`.
  - Optional: You could install `psycopg2-binary`, but psycopg2 may not support the newest Python versions promptly (e.g. 3.13). Prefer psycopg v3.



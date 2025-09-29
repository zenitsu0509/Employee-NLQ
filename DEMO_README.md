# Live Demo Guide (≈7 minutes)

This guide walks you through a quick end‑to‑end demo of the NLP Query Engine: connect a database, ingest documents, run SQL/document/hybrid queries, and highlight performance and features.

## Prerequisites (before the demo)

- Backend running at <http://localhost:8000>
- Frontend running at <http://localhost:5173>
- PostgreSQL running with an `employees` database
- Connection string (for local Dockerized Postgres):
  - `postgresql+psycopg://user:password@localhost:5432/employees`
- Seeded sample data (departments + employees). If empty, see the "Appendix: Seed sample data" section.
- Have a few small text/PDF docs handy (e.g., resumes mentioning "Python" and "AWS", policy docs, etc.).

Tip: If running with Docker Compose, start services ahead of time so they’re warm:

```bash
# from project root
docker compose up -d postgres
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
cd frontend && npm run dev
```

---

## 1) Data Ingestion (≈2 minutes)

### A. Connect to a database and show schema discovery

- In the frontend (<http://localhost:5173>), paste the connection string into "Connection string".
- Click "Test & Discover Schema".
- Show the success alert and the "Discovered Schema" section populating with:
  - Tables, columns, types
  - Sample rows
  - Relationships (if present)

Notes:

- The backend auto-normalizes Postgres URLs to prefer psycopg v3.
- Inside Docker Compose, use host `postgres` instead of `localhost` in the URL.

### B. Upload multiple documents and show processing

- Click "Select files" and choose multiple files (PDF, DOCX, TXT, CSV, JSON).
- Show the ingestion status alert: processed/total and status chip (IN_PROGRESS → COMPLETED).
- Mention that files are chunked and embedded automatically.

### C. Display ingestion status and success metrics

- While processing, point out the live status updates.
- After completion, highlight that the document matches will appear in query results (Document/Hybrid queries).

---

## 2) Query Interface (≈3 minutes)

Run exactly six queries through the UI using the text box and "Run query".

### A. Two SQL queries (show table results)

1. "List employees with their department names"
2. "Show average salary by department"

What to show:

- The results table with rows
- The "Query type" chip should show SQL
- Metrics chips (response_ms, cache_hit)

### B. Two document queries (show relevant chunks)

1. "Find documents mentioning Python and AWS"
2. "Show documents related to onboarding policy"

What to show:

- The "Document Matches" section with snippet cards
- The "Query type" chip should show DOCUMENT

### C. Two hybrid queries (combined results)

1. "Show employees in engineering and related documents about Python"
2. "Top paid employees and related documents mentioning cloud"

Tips for hybrid:

- If you only see document results, add a table word like "employees" or a department name.
- If you only see SQL results, include a document keyword (e.g., "Python", "policy").

### D. Demonstrate cache hits and error handling

- Re-run one of the above queries; point out the `cache_hit` metric flips to true.
- Submit an empty query to trigger a UI validation error (or use an obviously invalid one to show server error handling).

---

## 3) Performance & Features (≈2 minutes)

- Open two browser tabs and run different queries concurrently to demonstrate responsiveness.
- Highlight the response time metrics (response_ms) in the chips.
- Scroll to "Discovered Schema" to demonstrate schema visualization: tables, columns, and any relationships.
- Export results:
  - If your UI includes an export control, click it now; otherwise:
  - Use the API via curl to save a query result to a JSON file (see Appendix), or copy from the results table.

---

## Appendix

### Seed sample data (Postgres)

If your database is empty, run this once to create tables and seed rows:

```bash
# from project root with docker compose
docker compose exec -T postgres psql -U user -d employees -v ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE IF NOT EXISTS departments (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS employees (
  id SERIAL PRIMARY KEY,
  first_name TEXT NOT NULL,
  last_name  TEXT NOT NULL,
  email      TEXT UNIQUE NOT NULL,
  title      TEXT,
  salary     NUMERIC(12,2),
  hire_date  DATE DEFAULT CURRENT_DATE,
  department_id INT REFERENCES departments(id)
);

INSERT INTO departments (name) VALUES
  ('HR'), ('Engineering'), ('Sales'), ('Finance')
ON CONFLICT (name) DO NOTHING;

INSERT INTO employees (first_name,last_name,email,title,salary,hire_date,department_id) VALUES
  ('Alice','Johnson','alice.johnson@example.com','HR Manager',85000,'2023-01-15',(SELECT id FROM departments WHERE name='HR')),
  ('Bob','Smith','bob.smith@example.com','Software Engineer',110000,'2022-07-01',(SELECT id FROM departments WHERE name='Engineering')),
  ('Carol','Lee','carol.lee@example.com','Sales Associate',75000,'2024-03-10',(SELECT id FROM departments WHERE name='Sales')),
  ('David','Kim','david.kim@example.com','Financial Analyst',90000,'2021-11-20',(SELECT id FROM departments WHERE name='Finance')),
  ('Eva','Patel','eva.patel@example.com','Senior Engineer',130000,'2020-05-05',(SELECT id FROM departments WHERE name='Engineering'))
ON CONFLICT (email) DO NOTHING;

SELECT d.name, COUNT(*) AS employees
FROM employees e JOIN departments d ON d.id = e.department_id
GROUP BY d.name ORDER BY d.name;
SQL
```

### Helpful API checks

Health:

```bash
curl http://localhost:8000/health
```

Connect to DB:

```bash
curl -X POST http://localhost:8000/api/ingest/database \
  -H "Content-Type: application/json" \
  -d '{"connection_string": "postgresql+psycopg://user:password@localhost:5432/employees"}'
```

Run a query and save results to file (for export demo):

```bash
curl -s -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"connection_string":"postgresql+psycopg://user:password@localhost:5432/employees","query":"Show average salary by department","top_k":10}' \
  > avg-salary.json
```

### Troubleshooting

- 405 Method Not Allowed on /api/ingest/database:
  - Use POST, not GET. The UI uses POST; verify in the Network tab.
- CORS preflight (OPTIONS) errors:
  - Backend includes CORS; ensure origin is <http://localhost:5173> (or add to CORS_ORIGINS env).
- "No module named psycopg2":
  - Use `postgresql+psycopg://...` in connection strings; backend auto-normalizes, but make it explicit in demos.

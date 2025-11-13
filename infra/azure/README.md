# Azure deployment guide (cost-sensitive, uses $100 free credits)

This repo now ships with production Dockerfiles for backend and frontend and a sample compose. Below are two recommended Azure deployment paths; start with Option A for lowest cost and least ops.

## Option A — Container Apps (backend + worker) + Azure Database for PostgreSQL + Static Web Apps (frontend)

- Best for: low-cost, scalable, quick to set up.
- Est. monthly (dev):
  - Azure Container Apps (consumption): $0–$10 depending on traffic (scales to 0)
  - Azure Database for PostgreSQL Flexible Server (B1ms + 32GB): ~$30–$40
  - Azure Static Web Apps (Free plan): $0
  - Optional Azure Cache for Redis (Basic C0): ~$16 (you can skip; in-memory cache is default)

### Architecture

- Frontend: built SPA hosted on Azure Static Web Apps.
- Backend: FastAPI in Azure Container Apps (ACA) with health endpoint at `/health`.
- Worker: optional RQ worker in ACA using the same image with command override `python -m backend.worker`.
- Database: Azure Database for PostgreSQL Flexible Server (enable `pgvector` extension).

### 1) Provision Azure resources

- Resource group
- Postgres Flexible Server (Public access during dev; later restrict by VNet + IP allowlist)
- Enable `pgvector`:
  - psql: `CREATE EXTENSION IF NOT EXISTS vector;`
- Container Apps environment (consumption)
- Optional: Azure Container Registry (ACR) if you want CI to push images (alternatively use GHCR)

### 2) Connection strings and env

Required env vars for backend/worker:

- `DATABASE_URL` — Full SQLAlchemy URL (e.g. `postgresql+psycopg://<user>:<pass>@<host>:5432/<db>`)
- `VECTOR_DB_URL` — Optional; defaults to `DATABASE_URL`; used by Alembic pgvector tables
- `GROQ_API_KEY` — Your Groq API key (or switch provider in `config.yml`)
- `CORS_ORIGINS` — Comma-separated list; include your frontend domain (e.g., `https://<your-swa>.azurestaticapps.net`)

### 3) Build and push images

You can use GitHub Actions or local CLI. Images:

- Backend/Worker image (same image): built from `backend/Dockerfile`
- Frontend: build with `frontend/Dockerfile` or deploy via Static Web Apps (recommended)

Example tags:

- `backend: <registry>/employee-nlq-backend:latest`
- `frontend: <registry>/employee-nlq-frontend:latest` (if containerizing)

### 4) Deploy Container Apps

- Create ACA for backend: image `<registry>/employee-nlq-backend:latest`, port 8000, ingress external, health `/health`
- Create ACA for worker: same image, no ingress, command override `python -m backend.worker`
- Set environment variables on both apps (worker needs at least `GROQ_API_KEY`, `DATABASE_URL`, `VECTOR_DB_URL`, `REDIS_URL` if queue is enabled)
- Scale: min=0, max=1–3 for dev

### 5) Deploy frontend (Static Web Apps)

- App location: `frontend`
- Build command: `npm ci && npm run build`
- Output location: `frontend/dist`
- Set `VITE_API_BASE_URL` in the SWA build environment to your backend public URL (e.g., `https://<backend>.<region>.azurecontainerapps.io`)

### 6) Database migrations

The backend image runs Alembic on start. Ensure `DATABASE_URL`/`VECTOR_DB_URL` are set and database is reachable.


## Option B — App Service for Containers (backend) + PostgreSQL + Static Web Apps

- Very similar to Option A, but uses App Service instead of Container Apps. Good if you prefer App Service features like easy custom domains, staging slots, and always-on.


## Bring Your Own Database: how it works after deployment

Your cloud backend must reach the database over the network via the `DATABASE_URL` you provide.

- Recommended: point `DATABASE_URL` at a managed Azure PostgreSQL instance you control.
- If a user wants the cloud backend to query their own local Docker Postgres, they must expose it securely to the internet:
  - Use a tunneling solution (Tailscale, Cloudflare Tunnel, ngrok TCP) and restrict by auth/IP allowlist.
  - Or set up a VPN (Azure VNet + Point-to-Site) and route traffic privately.
  - Directly opening a home IP + port-forward is not recommended for security.
- Alternative: let users run the entire stack locally with `docker-compose` (already supported) which keeps DB local with no exposure.


## CI/CD (high level)

- Push to `main` builds and pushes backend image to ACR/GHCR.
- Deploy or update ACA revision with new image tag.
- SWA auto-builds frontend on push (if SWA GitHub integration is enabled) with `VITE_API_BASE_URL` set in SWA environment.

## Frontend on Vercel (alternative to SWA)

If you prefer Vercel for the frontend while keeping the backend on Azure:

- Connect this GitHub repo to a Vercel project and set the root directory to `frontend`.

- In Vercel Project Settings → Environment Variables, add:

  - `VITE_API_BASE_URL = https://<backend>.<region>.azurecontainerapps.io`

- Build command: `npm ci && npm run build` (Vercel will detect Vite/React automatically).

- Output directory: `dist` (Vercel auto-detects for Vite).

- CORS: set `CORS_ORIGINS` in Azure to include your Vercel domain (e.g., `https://your-app.vercel.app`).

- No Vercel rewrites are necessary since the frontend calls the backend via `VITE_API_BASE_URL`.

See `.env.example` for local variables and `docker-compose.yml` for local testing.

# Export Incentive Assurance Platform

Phase 0 is a production-leaning foundation for a multi-tenant SaaS that helps Indian exporters recover and assure incentives, prepare documentation, and monitor compliance. This phase intentionally stops at the secure skeleton: auth, tenancy, audit logging, schema, seed data, and an empty dashboard shell.

## What Phase 0 includes

- `pnpm` + Turborepo monorepo scaffold
- FastAPI backend with:
  - Pydantic settings
  - SQLAlchemy 2.0 models
  - Alembic migration wiring
  - JWT auth with organization creation on signup
  - RBAC scaffold (`owner`, `staff`, `read_only`)
  - append-only audit logging
  - tenant-safe repository layer and tests
- React + Vite frontend with:
  - dark-mode dashboard shell
  - signup/login flows
  - authenticated overview page
  - TanStack Query API client
  - workspace packages for shared types and UI primitives
- Docker Compose for `postgres`, `redis`, `api`, and `web`
- GitHub Actions CI for backend/frontend linting, type checks, and tests
- Demo seed data

## Repo layout

```text
apps/
  api/       FastAPI app, migrations, tests, seed script
  web/       React app
packages/
  shared/    Shared TypeScript types
  ui/        Shared UI primitives
```

Legacy top-level `backend/` and `frontend/` folders from the previous project were left untouched and are not used by this platform.

## Quick start

1. Create your environment file.

```powershell
Copy-Item .env.example .env
```

2. Start everything.

```powershell
docker compose up --build
```

3. Open the app.

- Web: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`
- API health: `http://localhost:8000/api/v1/health`

## Demo account

The API container runs migrations, seeds the demo tenant, and then starts the server.

- Email: `demo@example.com`
- Password: `DemoPassword123!`

You can also create a fresh tenant from the signup page. Signup creates:

- the organization
- the owner membership
- the initial JWT session

## Local development without Docker

### Backend

```powershell
cd apps\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item ..\..\.env.example .env
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/export_assurance"
$env:REDIS_URL="redis://localhost:6379/0"
$env:JWT_SECRET_KEY="change-me-in-production"
alembic upgrade head
python -m app.scripts.seed_demo
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
pnpm install
pnpm --filter web dev
```

## Useful commands

### Backend

```powershell
cd apps\api
pytest tests -q
ruff check app tests
mypy app
```

### Frontend

```powershell
pnpm lint
pnpm typecheck
```

## Phase 0 acceptance map

- `docker compose up --build` starts `postgres`, `redis`, `api`, and `web`
- signup provisions a tenant and owner user
- login returns a JWT-backed session
- the dashboard is protected
- tenant repository tests prove cross-tenant access is blocked
- CI runs lint, type-check, and test workflows

## Next phase

Phase 1 should begin only after you verify this scaffold runs cleanly in your environment. That phase will add CSV/Excel ingestion, the pure reconciliation engine, discrepancy dashboards, rate lookup, and PDF document generation.

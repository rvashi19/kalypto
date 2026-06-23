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

## Render deployment

This repo now includes a root-level `render.yaml` Blueprint for Render.

What it provisions:

- `kalypto-postgres` as Render Postgres
- `kalypto-redis` as Render Key Value
- `kalypto-api` as a Docker-based web service
- `kalypto-web` as a static site

What you still enter manually during the first Blueprint import:

- `FRONTEND_URL` for the API service
- `VITE_API_BASE_URL` for the frontend build

Recommended order in Render:

1. Import the repo as a Blueprint from `https://github.com/rvashi19/kalypto.git`
2. Let Render create the four resources from `render.yaml`
3. After Render assigns your service URLs, set:
   - `FRONTEND_URL=https://<your-static-site>.onrender.com`
   - `VITE_API_BASE_URL=https://<your-api-service>.onrender.com/api/v1`
4. Trigger a redeploy of both `kalypto-api` and `kalypto-web`

Notes:

- The API health check path is `/api/v1/health`
- The frontend includes a rewrite from `/*` to `/index.html` for React Router
- The free instance types are suitable for a demo only

## Phase 0 acceptance map

- `docker compose up --build` starts `postgres`, `redis`, `api`, and `web`
- signup provisions a tenant and owner user
- login returns a JWT-backed session
- the dashboard is protected
- tenant repository tests prove cross-tenant access is blocked
- CI runs lint, type-check, and test workflows

## Next phase

Phase 1 should begin only after you verify this scaffold runs cleanly in your environment. That phase will add CSV/Excel ingestion, the pure reconciliation engine, discrepancy dashboards, rate lookup, and PDF document generation.

## Country Compliance Requirement Checker

This feature is available behind the authenticated dashboard. It helps an exporter check destination-country import documents, certificates, labeling, restrictions, inspection/testing needs, buyer-side questions, sources, confidence, and a mandatory compliance disclaimer.

### How to run the checker

1. Start the stack with `docker compose up --build`.
2. Log in with the demo account: `demo@example.com` / `DemoPassword123!`.
3. Open the dashboard and use the `Country Compliance Requirement Checker` panel.
4. Try the seeded examples:
   - `Mango fruit beverage`, HSN `200989`, destination `Canada`, category `beverages`.
   - `Packaged cashew dry fruits`, HSN `080132`, destination `United Arab Emirates`, category `dry fruits`.
   - `Cotton knit shirt`, HSN `610910`, destination `UK`, category `textiles`.

### How to run scraper or source updates

The checker is retrieval-first. It does not trust live scraped text automatically. Use `/api/v1/compliance/scrape/run` to capture a source page, review the extracted text, then send verified structured records to `/api/v1/compliance/scrape/ingest`.

Environment variables:

```bash
COMPLIANCE_SCRAPER_PROVIDER=http
COMPLIANCE_ALLOW_PRIVATE_SCRAPE=false
COMPLIANCE_SCRAPER_USER_AGENT="KalyptoComplianceBot/0.1 (+https://kalypto.local; review-only)"
COMPLIANCE_STORE_BACKEND=postgres
COMPLIANCE_REFRESH_INTERVAL_DAYS=3
FIRECRAWL_API_KEY=
TAVILY_API_KEY=
BRIGHT_DATA_API_KEY=
```

Production scraper behavior:

- `http` fetches live HTML/text pages, extracts readable text, hashes the source, and blocks localhost/private-network URLs by default.
- `firecrawl` can be enabled for richer page/PDF extraction by setting `COMPLIANCE_SCRAPER_PROVIDER=firecrawl` and `FIRECRAWL_API_KEY`.
- Scraped source text is stored as a review snapshot only. It never becomes approved compliance advice automatically.
- Changed sources create `needs_review` records under `/api/v1/compliance/scrape/changes`.
- Operators review or ignore source changes through `/api/v1/compliance/scrape/changes/{change_id}/review`.

Recommended live data stack:

- Use Tavily Search API to discover official source pages.
- Use Firecrawl API to extract official pages and PDFs into markdown/JSON for review.
- Use Bright Data Web Unlocker only for official sources that block normal extraction.

### How to add countries or product categories

Add verified records through `/api/v1/compliance/scrape/ingest`. The ingestion service creates tenant-scoped country/category rows automatically. Current supported scope is Canada, USA, Netherlands/EU, UK, United Arab Emirates, and Saudi Arabia with food/agri, spices, dry fruits, beverages, and textiles. Add new countries only after confirming source coverage, freshness rules, and review ownership.

### Confidence scoring

Each stored requirement has an operator-provided `confidence_score` from `0` to `100`. Retrieval adds small boosts for HSN and product keyword matches. The final response is:

- `High` when source-backed records strongly match the product context and there are no major unresolved questions.
- `Medium` when the country/category matches but product-specific or buyer-side checks remain.
- `Low` when records are missing, generic, or uncertain.

Every answer includes sources, last checked date, unresolved questions, confidence, and the disclaimer that the output is compliance assistance, not legal/customs advice.
### MongoDB compliance knowledge store

Compliance requirements can now be served from MongoDB while the rest of the SaaS stays on Postgres. This keeps auth, audit logs, shipments, claims, and tenant records relational, but lets country compliance data remain flexible and fast.

Default local/Render mode:

```bash
COMPLIANCE_STORE_BACKEND=postgres
MONGODB_URL=
MONGODB_DATABASE=kalypto
COMPLIANCE_REFRESH_INTERVAL_DAYS=3
```

To use MongoDB in production, create a MongoDB Atlas cluster, set `MONGODB_URL`, then change `COMPLIANCE_STORE_BACKEND` to `mongo`.

The Mongo collections are:

- `compliance_requirements`: active approved records used by the checker.
- `compliance_source_snapshots`: raw scraped source snapshots and content hashes.
- `compliance_source_changes`: source changes marked `needs_review`.

Source checks should run every 3-4 days:

```bash
python -m app.scripts.refresh_compliance_sources
```

That job re-scrapes due sources, stores a new snapshot, compares the content hash, and marks changed sources as `needs_review`. It does not automatically publish new compliance answers. A human still reviews source changes and ingests approved structured records.
## Compliance checker V0 evidence workflow

The Country Compliance Requirement Checker is deliberately cache-first and review-first:

- The checker answers only from tenant-scoped evidence records with `status=active`, `review_status=approved`, and a non-expired `expires_at`.
- Scraped source changes are saved as snapshots/change records with `needs_review`; they are not published into approved answers automatically.
- Pending, rejected, stale, or missing evidence returns a safe low-confidence response instead of a guessed compliance answer.
- The required safety message is always shown: `This is compliance assistance based on available source-backed records. It is not legal, customs, or regulatory advice. Verify requirements with the importer, customs broker, or official authority before shipment.`

Freshness rules in V0:

- beverages, dry fruits, spices, food/agri: 15 days
- textiles: 30 days
- restricted/prohibited alerts: 7 days
- general import-document evidence outside the short categories: 60 days

To run locally without Docker, keep `COMPLIANCE_STORE_BACKEND=postgres` and use the SQLite fallback database only for demos/tests. `apps/api/local_kalypto.db` is local-only, ignored by git, and must not be committed.

To refresh source snapshots:

```powershell
cd apps\api
$env:COMPLIANCE_STORE_BACKEND="postgres"
python -m app.scripts.refresh_compliance_sources
```

The refresh output logs `source`, `content_hash`, whether content changed, whether a pending review record was created, and any source errors. After review, add approved structured evidence through the ingest endpoint or seed script.

Docker Compose is still the one-command path, but it requires Docker Desktop installed and available on PATH.

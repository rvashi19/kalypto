# ExportPilot AI — Export Document & Incentive Audit Platform

An AI-assisted SaaS for Indian exporters to prepare shipment documents, identify discrepancies,
and review source-backed compliance requirements. Incentive and compliance outputs are
decision support only and require human verification.

Built on a production-grade multi-tenant monorepo: FastAPI + PostgreSQL + React + Groq AI.

---

## What's in Phase 1 (current)

### 5-step shipment audit workflow

1. **Shipment Profile** — capture product, HSN code, destination country, Incoterm, payment term, shipment mode, and FOB value
2. **Document Checklist** — AI generates a tailored checklist covering required, optional, country-specific, bank/payment, and incentive-refund documents based on the shipment profile
3. **Upload Documents** — upload Commercial Invoice, Packing List, Bill of Lading/AWB, Certificate of Origin, Shipping Bill, and more
4. **Verification Report** — AI audits cross-document fields (buyer name, HSN code, FOB value, weights, port, Incoterm) and estimates eligible government incentives with action items
5. **Expert Review** — connect with a human CHA/DGFT consultant for a final review

### AI capabilities (Groq llama-3.3-70b)

- Generates document checklists tailored to Incoterm, shipment mode, destination country, HSN category, and payment terms
- Detects mismatches across documents — the exact fields Indian Customs checks during assessment and examination
- Uses only operator-seeded, versioned rate records for incentive calculations; missing rates are
  reported instead of invented
- Produces a Finance Readiness Score (0–100) and prioritised action list
- Generates eBRC and GST filing reminders

### Platform features

- Multi-tenant SaaS — each organisation is fully isolated at the database layer
- JWT authentication with RBAC (owner / staff / read_only)
- Append-only audit log on every write
- File upload with document-type tagging
- CSV/XLSX bulk shipment import with row-level error reporting
- Stored PDF generation for proforma invoices, commercial invoices, and packing lists
- Country Compliance Requirement Checker for approved, source-backed destination-country evidence
- Automated source snapshots, change detection, and an operator review queue
- Dark-mode React dashboard shell

---

## Repo layout

```
apps/
  api/       FastAPI + SQLAlchemy 2.0 + Alembic + Groq AI services
  web/       React + Vite + TanStack Query
packages/
  shared/    Shared TypeScript types (shipment, document, verification schemas)
  ui/        Shared UI primitives
```

---

## Quick start (Docker)

```bash
# 1. Copy and fill in environment variables
cp .env.example .env
# Required: GROQ_API_KEY (get a free key at console.groq.com)

# 2. Start everything
docker compose up --build

# 3. Open the app
#    Web:      http://localhost:5173
#    API docs: http://localhost:8000/docs
#    Health:   http://localhost:8000/api/v1/health
```

### Demo account

The API container runs migrations, seeds a demo tenant, then starts the server.

- Email: `demo@example.com`
- Password: `DemoPassword123!`

Or create a fresh tenant from the signup page.

---

## Environment variables

| Variable | Description |
|---|---|
| `POSTGRES_DB` | Database name (default: `export_assurance`) |
| `POSTGRES_USER` | Postgres user |
| `POSTGRES_PASSWORD` | Postgres password |
| `DATABASE_URL` | Full SQLAlchemy connection string |
| `JWT_SECRET_KEY` | Secret for signing JWTs — **change in production** |
| `FRONTEND_URL` | CORS allowed origin for the web app |
| `VITE_API_BASE_URL` | API base URL used by the frontend |
| `GROQ_API_KEY` | Groq API key for AI features |
| `GROQ_MODEL` | Model to use (default: `llama-3.3-70b-versatile`) |
| `UPLOAD_DIR` | Directory for uploaded documents (default: `/tmp/kalypto_uploads`) |
| `COMPLIANCE_STORE_BACKEND` | Compliance evidence backend: `postgres` by default, `mongo` optional |
| `COMPLIANCE_SCRAPER_PROVIDER` | Compliance source refresh provider: built-in `http` by default |
| `COMPLIANCE_REFRESH_INTERVAL_DAYS` | Source refresh cadence for due-source checks |
| `MONGODB_URL` | Optional MongoDB URL when `COMPLIANCE_STORE_BACKEND=mongo` |

Copy `.env.example` to `.env` and fill in your values. The `.env` file is gitignored — never commit it.

---

## Local development without Docker

### Backend

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../../.env.example .env       # then fill in values

alembic upgrade head
python -m app.scripts.seed_demo
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
pnpm install
pnpm --filter web dev
```

---

## Useful commands

```bash
# Backend
cd apps/api
pytest tests -q
ruff check app tests
mypy app

# Frontend
pnpm lint
pnpm typecheck
```

---

## API overview

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Create organisation + owner account |
| POST | `/api/v1/auth/login` | Login, returns JWT |
| GET | `/api/v1/shipments` | List shipments for current organisation |
| POST | `/api/v1/shipments` | Create a new shipment |
| POST | `/api/v1/shipments/import` | Import CSV/XLSX shipments with row-level errors |
| GET | `/api/v1/shipments/{id}` | Get shipment details |
| DELETE | `/api/v1/shipments/{id}` | Delete a shipment |
| GET | `/api/v1/shipments/{id}/checklist` | AI-generated document checklist |
| GET | `/api/v1/shipments/{id}/documents` | List uploaded documents |
| POST | `/api/v1/shipments/{id}/documents` | Upload a document |
| POST | `/api/v1/shipments/{id}/documents/generate/{type}` | Generate and store a draft PDF |
| GET | `/api/v1/shipments/{id}/documents/{document_id}/download` | Download a tenant-scoped document |
| POST | `/api/v1/shipments/{id}/reconcile` | Run and persist deterministic reconciliation |
| GET | `/api/v1/shipments/{id}/verify` | Run AI verification report |
| GET | `/api/v1/dashboard/discrepancies` | Aggregate persisted discrepancy and potential-amount data |
| GET | `/api/v1/rates` | List operator-seeded versioned rates |
| POST | `/api/v1/rates/import` | Import a reviewed rate CSV |
| GET | `/api/v1/compliance/options` | Supported countries/categories for compliance checker |
| POST | `/api/v1/compliance/checker/answer` | Source-backed compliance checker answer |
| POST | `/api/v1/compliance/scrape/run` | Capture source snapshot for review |
| POST | `/api/v1/compliance/scrape/ingest` | Ingest manually reviewed compliance evidence |
| GET | `/api/v1/compliance/scrape/due` | List sources due for refresh |
| GET | `/api/v1/compliance/scrape/changes` | List source changes awaiting review |

Full interactive docs at `http://localhost:8000/docs`.

---

## Country Compliance Requirement Checker

The checker is available in the web app at `/compliance`.

Initial scope is intentionally limited to:

- Countries: Canada, USA, Netherlands/EU, UK, United Arab Emirates, Saudi Arabia
- Categories: food/agri, spices, dry fruits, beverages, textiles

The checker is cache-first and review-first:

- Final answers use only tenant-scoped records with `status=active`, `review_status=approved`, and fresh `expires_at`.
- Scraped source changes create snapshots/change records for review; they are not auto-published.
- Pending, stale, unsupported, or missing evidence returns a low-confidence safe response instead of guessed compliance advice.
- Every response includes sources, confidence, last checked date, unresolved questions, and this disclaimer:

`This is compliance assistance based on available source-backed records. It is not legal, customs, or regulatory advice. Verify requirements with the importer, customs broker, or official authority before shipment.`

To refresh due source snapshots:

```bash
cd apps/api
python -m app.scripts.refresh_compliance_sources
```

`apps/api/local_kalypto.db` is local-only and ignored by git.

---

## Render deployment

A `render.yaml` Blueprint is included for one-click Render deployment.

Resources provisioned:
- `kalypto-postgres` - private managed Postgres
- `kalypto-redis` - private persistent Key Value
- `kalypto-api` - Docker service with persistent document storage
- `kalypto-web` - static site with security headers
- `kalypto-compliance-refresh` - daily compliance refresh cron

After the Blueprint import, set these manually in the Render dashboard:
- `FRONTEND_URL` → your static site URL (e.g. `https://kalypto-web.onrender.com`)
- `VITE_API_BASE_URL` → your API URL + `/api/v1`
- `GROQ_API_KEY` → your Groq API key
- `XAI_API_KEY` → your xAI key for the documentation assistant

Then trigger a redeploy of both services.

---

## Production safeguards

- Never commit `.env`, keys, credentials, uploads, generated documents, or local databases.
- Production startup does not create the demo account unless `SEED_DEMO_DATA=true`.
- Scraped compliance text is quarantined as a snapshot and never auto-published as approved advice.
- Rate and HSN results must come from tenant-scoped `RateTable` records with source, effective date,
  version stamp, confidence, and a visible CHA/customs-broker verification warning.
- Government portal submission is intentionally not implemented.
- Render paid services and the persistent disk incur charges; review the Blueprint before syncing.

## Remaining roadmap

- Persist deterministic reconciliation results and money-at-risk history instead of relying only on
  an on-demand AI verification response.
- Add operator CRUD/import UI for versioned incentive rate notifications.
- Add government connector adapters with mocks and manual-upload fallbacks only.
- Add external uptime, error tracking, backup restore drills, and an independent penetration test.

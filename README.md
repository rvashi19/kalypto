# ExportPilot AI — Export Document & Incentive Audit Platform

An AI-powered SaaS for Indian exporters to audit shipment documents, catch cross-document discrepancies, and maximize government incentive recovery (Duty Drawback, RoDTEP, IGST, EPCG, and more).

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
- Estimates eligible incentive amounts for Duty Drawback, RoDTEP, IGST Refund, RoSCTL, Advance Authorisation, EPCG, and Interest Equalisation Scheme
- Produces a Finance Readiness Score (0–100) and prioritised action list
- Generates eBRC and GST filing reminders

### Platform features

- Multi-tenant SaaS — each organisation is fully isolated at the database layer
- JWT authentication with RBAC (owner / staff / read_only)
- Append-only audit log on every write
- File upload with document-type tagging
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
| GET | `/api/v1/shipments/{id}` | Get shipment details |
| DELETE | `/api/v1/shipments/{id}` | Delete a shipment |
| GET | `/api/v1/shipments/{id}/checklist` | AI-generated document checklist |
| GET | `/api/v1/shipments/{id}/documents` | List uploaded documents |
| POST | `/api/v1/shipments/{id}/documents` | Upload a document |
| GET | `/api/v1/shipments/{id}/verify` | Run AI verification report |

Full interactive docs at `http://localhost:8000/docs`.

---

## Render deployment

A `render.yaml` Blueprint is included for one-click Render deployment.

Resources provisioned:
- `kalypto-postgres` — managed Postgres
- `kalypto-redis` — managed Redis
- `kalypto-api` — Docker-based web service
- `kalypto-web` — static site

After the Blueprint import, set these manually in the Render dashboard:
- `FRONTEND_URL` → your static site URL (e.g. `https://kalypto-web.onrender.com`)
- `VITE_API_BASE_URL` → your API URL + `/api/v1`
- `GROQ_API_KEY` → your Groq API key

Then trigger a redeploy of both services.

---

## Phase 2 roadmap

- OCR-based field extraction from uploaded PDFs (auto-populate discrepancy checker)
- HSN code lookup and rate tables for Duty Drawback and RoDTEP
- eBRC tracking and GST refund status monitoring
- Shipping Bill generation assistance
- Buyer verification workflow
- Email alerts for upcoming EPCG/Advance Authorisation obligation deadlines

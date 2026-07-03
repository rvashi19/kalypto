# KALYPTO — Agent Guide

Export-compliance SaaS for Indian exporters (HSN finder, incentive finder, export
quote, document builder, country compliance checker).

## Stack
- **Monorepo:** pnpm 9 workspaces + Turborepo.
- **Backend:** `apps/api` — Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic
  settings, PostgreSQL (SQLite for tests), Redis, optional MongoDB. LLM via
  Groq/OpenAI/xAI (`AI_PROVIDER`).
- **Frontend:** `apps/web` — React 18, Vite 6, TypeScript, React Router, TanStack
  Query, Tailwind. Shared types in `packages/shared`.
- **Deploy:** Render (backend, tracks `chore/free-tier-deployment`), Vercel
  (frontend, tracks `main`), Neon Postgres, Cloudflare R2.

## Commands
Backend (`apps/api`):
- Test: `python -m pytest` (SQLite; sets `DATABASE_URL` in `tests/conftest.py`)
- Lint: `python -m ruff check app/ tests/`
- Migrate: `python -m alembic upgrade head`
- Run: `uvicorn app.main:app --reload`

Frontend / monorepo (repo root):
- Typecheck: `pnpm typecheck` (or `npx tsc --noEmit` in `apps/web`)
- Lint: `pnpm lint`
- Build: `pnpm build`
- Shared types: `pnpm --filter @repo/shared build` (rebuild after editing `packages/shared`)

## Conventions
- Backend files carry `# ruff: noqa: E501` where long DDL/strings are unavoidable;
  otherwise keep lines ≤100.
- Alembic migrations are **idempotent** (inspect table names before create).
- Multi-tenant: everything is scoped by `tenant_id`; use the `CurrentUser` /
  `DbSession` dependency pattern.
- Auth response models must never expose password hashes or tokens.
- Compliance module: official evidence is the source of truth; AI output is
  `pending_review` until an admin approves. Only whitelisted official domains are
  ever fetched.

## Coding rules & review agents
Stack-specific coding rules live in `.claude/rules/` (python, react, typescript,
common). Consult them when writing or reviewing code. Specialized review subagents
are available in `.claude/agents/` — e.g. `fastapi-reviewer`, `python-reviewer`,
`database-reviewer`, `react-reviewer`, `typescript-reviewer`, `security-reviewer`.
Prefer the matching reviewer before merging changes to that surface.

Rules and agents are adapted from ECC (MIT) — see `.claude/ATTRIBUTION.md`.

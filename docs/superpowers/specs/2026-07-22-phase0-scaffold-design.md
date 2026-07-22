# Phase 0 Scaffold — Design Spec

**Date:** 2026-07-22
**Session:** scaffold (TASK-000)
**PRD ref:** §11.2 Repository Structure, §16 Phase 0
**Status:** Approved

---

## 1. Scope

This session adds everything that the schema session did NOT build:

- Full monorepo directory layout per PRD §11.2
- FastAPI bootstrap in `services/orchestrator-api/src/` (app entry, config, middleware stubs, health endpoint)
- Next.js 14 App Router shells for `apps/candidate-web/` and `apps/console-web/`
- `services/realtime-gateway/` Node.js skeleton
- `services/ingestion-service/` Python skeleton
- `agents/` — 8 folder skeletons
- `packages/shared-types/` and `packages/prompt-library/` stubs
- `infra/docker/` and `infra/terraform/` placeholders
- Root `docker-compose.yml` (extends existing orchestrator-api compose)
- Root `.env.example`
- `pnpm-workspace.yaml` + root `package.json`
- `.github/workflows/ci.yml` — lint + test + build

**Out of scope this session:** auth/RBAC implementation, any agent logic, dashboards, resume ingestion.

---

## 2. Repository Layout

```
ARAP1/
├── apps/
│   ├── candidate-web/          # Next.js 14, App Router, Tailwind — minimal UI
│   └── console-web/            # Next.js 14, App Router, Tailwind — dense data UI
├── services/
│   ├── orchestrator-api/       # EXISTING — FastAPI + SQLAlchemy (schema session)
│   ├── realtime-gateway/       # Node.js skeleton
│   └── ingestion-service/      # Python skeleton
├── agents/
│   ├── resume_analysis/
│   ├── job_description/
│   ├── question_generation/
│   ├── evaluation/
│   ├── behavior_analysis/
│   ├── scoring/
│   ├── recommendation/
│   └── report_generator/
├── packages/
│   ├── shared-types/           # TS + Pydantic schema stubs
│   └── prompt-library/         # Versioned prompt template stubs
├── infra/
│   ├── docker/                 # Per-service Dockerfiles
│   └── terraform/              # IaC placeholder
├── .github/workflows/ci.yml
├── docker-compose.yml          # Root — all services + pgvector containers
├── .env.example
├── pnpm-workspace.yaml
└── package.json                # Root (private: true)
```

---

## 3. FastAPI Bootstrap (`services/orchestrator-api/src/`)

New files added alongside existing `src/models/`:

### `src/config.py`
Pydantic `BaseSettings` reading from environment:
- `DATABASE_URL` (required)
- `SECRET_KEY` (required)
- `ENVIRONMENT` (default: `development`)
- `LOG_LEVEL` (default: `info`)
- `APP_VERSION` (default: `0.1.0`)

### `src/main.py`
FastAPI app factory:
- Mounts middleware stack (in order): error handler → rate limiter → RBAC → auth
- Includes `api/health` router
- Sets `title`, `version` from config
- CORS configured from env (permissive in dev, restrictive in prod)

### `src/middleware/`
Four stub files — each is a proper FastAPI middleware class or exception handler that passes through all requests. Stubs intentionally minimal; auth/RBAC logic is the `auth` session's work.

| File | Stub behaviour |
|------|---------------|
| `auth.py` | `AuthMiddleware` — passes through; logs warning if no `Authorization` header |
| `rbac.py` | `RBACMiddleware` — passes through; placeholder for role extraction |
| `rate_limit.py` | `RateLimitMiddleware` — passes through; placeholder for token-bucket |
| `error_handler.py` | `http_exception_handler` + `unhandled_exception_handler` returning JSON `{detail, status_code}` |

### `src/api/health.py`
`GET /health` → `200 {"status": "ok", "version": "<APP_VERSION>"}`.
No DB check at Phase 0 (DB health belongs to the auth session once connection pooling is set up).

---

## 4. Next.js App Shells

Both apps: **Next.js 14, App Router, TypeScript, Tailwind CSS**.

### `apps/candidate-web/` — minimal, low-distraction
- Root layout: clean white background, centered content, no sidebar
- `app/page.tsx`: "ARAP — Candidate Portal" placeholder with a single CTA button
- `app/layout.tsx`: minimal HTML skeleton, Tailwind base styles
- `tailwind.config.ts`: neutral palette (slate/zinc), large readable font sizes
- No nav bar, no sidebar — PRD §11.1: "minimal low-distraction UI"

### `apps/console-web/` — dense, data-rich
- Root layout: sidebar nav (placeholder links), top bar, main content area
- `app/page.tsx`: "ARAP Console" dashboard placeholder with stat tile stubs
- `app/layout.tsx`: sidebar + topbar layout skeleton
- `tailwind.config.ts`: same base but compact spacing, smaller font sizes
- PRD §11.1: "dense data-rich UI"

### `packages/shared-types/`
- `package.json` with `name: "@arap/shared-types"`
- `src/index.ts` exporting empty barrel (filled in auth/Phase 1 sessions)
- `tsconfig.json` targeting ES2020

Both apps reference `@arap/shared-types` via `workspace:*` in their `package.json`.

---

## 5. Service Skeletons

### `services/realtime-gateway/`
- `package.json` (`name: "realtime-gateway"`, `main: "src/index.js"`, Node 20)
- `src/index.js`: `http.createServer` listening on `PORT` env var (default 3001), responds `{"status":"ok"}` on `GET /health`
- `.env.example` (local)

### `services/ingestion-service/`
- `pyproject.toml` (setuptools, Python ≥3.11)
- `src/__init__.py` + `src/main.py` stub (empty FastAPI app, `GET /health`)
- `tests/__init__.py`

### `agents/*/`
Each of the 8 agent folders gets:
- `__init__.py` (empty)
- `README.md` (one-line: agent name + PRD section ref)

### `packages/prompt-library/`
- `package.json` (`name: "@arap/prompt-library"`)
- `src/index.ts`: empty barrel
- `prompts/` directory with `.gitkeep`

---

## 6. Root Docker Compose

Root `docker-compose.yml` consolidates:
- `db-dev` (pgvector/pgvector:pg16, port 5433) — moved from `services/orchestrator-api/docker-compose.yml`
- `db-test` (pgvector/pgvector:pg16, port 5434)
- `orchestrator-api` service stub (build from `services/orchestrator-api/`, depends on `db-dev`)
- `realtime-gateway` service stub (build from `services/realtime-gateway/`)

The existing `services/orchestrator-api/docker-compose.yml` stays in place (used by pytest directly); root compose is the full-stack entrypoint.

---

## 7. `.env.example`

```
# Database
DATABASE_URL=postgresql://arap:arap@localhost:5433/arap_dev
TEST_DATABASE_URL=postgresql://arap:arap@localhost:5434/arap_test

# API
SECRET_KEY=change-me-in-production
ENVIRONMENT=development
LOG_LEVEL=info
APP_VERSION=0.1.0

# Next.js
NEXT_PUBLIC_API_URL=http://localhost:8000

# Gateway
PORT=3001
```

---

## 8. CI Pipeline (`.github/workflows/ci.yml`)

Three jobs, all on `ubuntu-latest`, triggered on push/PR to `main`:

**`lint`**
- Python: `ruff check services/orchestrator-api/src services/ingestion-service/src agents/`
- JS: `pnpm --filter "./apps/*" lint` (ESLint via Next.js built-in)

**`test`**
- Spins up pgvector service container (port 5434)
- `cd services/orchestrator-api && pip install -e ".[dev]" && pytest`
- JS: `pnpm --filter "./apps/*" build` (no JS unit tests yet at Phase 0)

**`build`**
- `pnpm --filter candidate-web build`
- `pnpm --filter console-web build`
- Python: `pip install -e services/orchestrator-api` (smoke install)

Jobs are independent; `test` depends on `lint` passing.

---

## 9. pnpm Workspace

`pnpm-workspace.yaml`:
```yaml
packages:
  - "apps/*"
  - "packages/*"
  - "services/realtime-gateway"
```

Root `package.json` (`private: true`):
```json
{
  "name": "arap",
  "private": true,
  "scripts": {
    "dev:candidate": "pnpm --filter candidate-web dev",
    "dev:console": "pnpm --filter console-web dev",
    "build": "pnpm --filter \"./apps/*\" build",
    "lint": "pnpm --filter \"./apps/*\" lint"
  }
}
```

---

## 10. Exit Criteria (this session)

- [ ] `pnpm install` at root resolves without errors
- [ ] `pnpm --filter candidate-web dev` boots on port 3000
- [ ] `pnpm --filter console-web dev` boots on port 3001 (or 3002)
- [ ] `uvicorn services.orchestrator-api.src.main:app` starts and `GET /health` returns 200
- [ ] All 44 existing pytest tests still pass
- [ ] GitHub Actions CI workflow file present and syntactically valid
- [ ] All 8 agent skeleton folders present with `__init__.py`
- [ ] Root `docker-compose.yml` present; `docker compose up -d` starts both DB containers

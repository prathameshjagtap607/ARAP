# Phase 0 Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the full ARAP monorepo layout per PRD §11.2 — pnpm workspaces, both Next.js app shells, FastAPI bootstrap with health endpoint, service/agent/package skeletons, root Docker Compose, .env.example, and GitHub Actions CI.

**Architecture:** pnpm workspaces at repo root linking `apps/*`, `packages/*`, and `services/realtime-gateway`. FastAPI bootstrap lives inside the existing `services/orchestrator-api/src/` package (`src` is the importable top-level package). Next.js 14 App Router for both frontend apps. Everything else is a skeleton — no business logic.

**Tech Stack:** Next.js 14.2.5 · React 18 · TypeScript 5 · Tailwind CSS 3 · FastAPI 0.111 · Pydantic Settings v2 · Python 3.11 · Node.js 20 · pnpm 9 · pytest · httpx · GitHub Actions

## Global Constraints

- Python ≥ 3.11; SQLAlchemy 2.x (existing); do NOT touch existing `src/models/` or `migrations/`
- Next.js 14 App Router only — no Pages Router
- pnpm for all JS package management; no npm or yarn
- TypeScript strict mode in all TS files
- All FastAPI deps in `services/orchestrator-api/pyproject.toml` only
- Existing 44 pytest tests must still pass after every Python task
- Working directory for Python tasks: `services/orchestrator-api/`
- Working directory for root-level tasks: repo root (`D:\staging\ARAP1`)
- Commit format: `[TASK-000] <type>: <description>`
- console-web dev port: 3002 (candidate-web: 3000, realtime-gateway: 3001)

---

## File Map

### Created in this plan

```
# JS workspace root
pnpm-workspace.yaml
package.json                                          (root, private:true)

# Shared packages
packages/shared-types/package.json
packages/shared-types/tsconfig.json
packages/shared-types/src/index.ts

packages/prompt-library/package.json
packages/prompt-library/src/index.ts
packages/prompt-library/prompts/.gitkeep

# Next.js apps
apps/candidate-web/package.json
apps/candidate-web/tsconfig.json
apps/candidate-web/next.config.ts
apps/candidate-web/tailwind.config.ts
apps/candidate-web/postcss.config.js
apps/candidate-web/src/app/globals.css
apps/candidate-web/src/app/layout.tsx
apps/candidate-web/src/app/page.tsx

apps/console-web/package.json
apps/console-web/tsconfig.json
apps/console-web/next.config.ts
apps/console-web/tailwind.config.ts
apps/console-web/postcss.config.js
apps/console-web/src/app/globals.css
apps/console-web/src/app/layout.tsx
apps/console-web/src/app/page.tsx
apps/console-web/src/components/Sidebar.tsx
apps/console-web/src/components/Topbar.tsx

# FastAPI bootstrap (inside existing orchestrator-api)
services/orchestrator-api/src/config.py
services/orchestrator-api/src/main.py
services/orchestrator-api/src/middleware/__init__.py
services/orchestrator-api/src/middleware/auth.py
services/orchestrator-api/src/middleware/rbac.py
services/orchestrator-api/src/middleware/rate_limit.py
services/orchestrator-api/src/middleware/error_handler.py
services/orchestrator-api/src/api/__init__.py
services/orchestrator-api/src/api/health.py
services/orchestrator-api/tests/api/__init__.py
services/orchestrator-api/tests/api/test_health.py

# Service skeletons
services/realtime-gateway/package.json
services/realtime-gateway/src/index.js

services/ingestion-service/pyproject.toml
services/ingestion-service/src/__init__.py
services/ingestion-service/src/main.py
services/ingestion-service/tests/__init__.py

# Agent skeletons (8×)
agents/resume_analysis/__init__.py
agents/resume_analysis/README.md
agents/job_description/__init__.py
agents/job_description/README.md
agents/question_generation/__init__.py
agents/question_generation/README.md
agents/evaluation/__init__.py
agents/evaluation/README.md
agents/behavior_analysis/__init__.py
agents/behavior_analysis/README.md
agents/scoring/__init__.py
agents/scoring/README.md
agents/recommendation/__init__.py
agents/recommendation/README.md
agents/report_generator/__init__.py
agents/report_generator/README.md

# Infra
infra/docker/.gitkeep
infra/terraform/.gitkeep

# Root config
docker-compose.yml
.env.example
.github/workflows/ci.yml
```

### Modified in this plan

```
services/orchestrator-api/pyproject.toml   add fastapi, uvicorn, pydantic-settings, httpx
```

---

## Task 1: pnpm Workspace Root

**Files:**
- Create: `pnpm-workspace.yaml`
- Create: `package.json` (repo root)

**Interfaces:**
- Produces: workspace resolution for `apps/*`, `packages/*`, `services/realtime-gateway` — all subsequent JS tasks depend on this

- [ ] **Step 1: Create `pnpm-workspace.yaml`** at repo root

```yaml
packages:
  - "apps/*"
  - "packages/*"
  - "services/realtime-gateway"
```

- [ ] **Step 2: Create root `package.json`** at repo root

```json
{
  "name": "arap",
  "version": "0.1.0",
  "private": true,
  "engines": {
    "node": ">=20",
    "pnpm": ">=9"
  },
  "scripts": {
    "dev:candidate": "pnpm --filter candidate-web dev",
    "dev:console": "pnpm --filter console-web dev",
    "build": "pnpm --filter \"./apps/*\" build",
    "lint": "pnpm --filter \"./apps/*\" lint"
  }
}
```

- [ ] **Step 3: Verify workspace file is valid**

Run from repo root:
```bash
pnpm --version
```
Expected: prints pnpm version ≥ 9. If pnpm not installed: `npm install -g pnpm`.

- [ ] **Step 4: Commit**

```bash
git add pnpm-workspace.yaml package.json
git commit -m "[TASK-000] chore: add pnpm workspace root"
```

---

## Task 2: packages/shared-types

**Files:**
- Create: `packages/shared-types/package.json`
- Create: `packages/shared-types/tsconfig.json`
- Create: `packages/shared-types/src/index.ts`

**Interfaces:**
- Consumed by: `apps/candidate-web` and `apps/console-web` via `@arap/shared-types`
- Produces: `@arap/shared-types` — empty barrel, filled in auth/Phase 1 sessions

- [ ] **Step 1: Create `packages/shared-types/package.json`**

```json
{
  "name": "@arap/shared-types",
  "version": "0.1.0",
  "private": true,
  "main": "./src/index.ts",
  "types": "./src/index.ts",
  "scripts": {
    "typecheck": "tsc --noEmit"
  },
  "devDependencies": {
    "typescript": "^5"
  }
}
```

- [ ] **Step 2: Create `packages/shared-types/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "declaration": true,
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create `packages/shared-types/src/index.ts`**

```typescript
// Shared TypeScript types between ARAP apps.
// Populated in auth session and Phase 1.

export type Role = "admin" | "user" | "candidate" | "client";

export interface ApiResponse<T> {
  data: T;
  status: number;
}
```

- [ ] **Step 4: Commit**

```bash
git add packages/
git commit -m "[TASK-000] feat: add shared-types package"
```

---

## Task 3: packages/prompt-library

**Files:**
- Create: `packages/prompt-library/package.json`
- Create: `packages/prompt-library/src/index.ts`
- Create: `packages/prompt-library/prompts/.gitkeep`

**Interfaces:**
- Produces: `@arap/prompt-library` — skeleton only; populated in M12 (prompt versioning)

- [ ] **Step 1: Create `packages/prompt-library/package.json`**

```json
{
  "name": "@arap/prompt-library",
  "version": "0.1.0",
  "private": true,
  "main": "./src/index.ts",
  "types": "./src/index.ts",
  "devDependencies": {
    "typescript": "^5"
  }
}
```

- [ ] **Step 2: Create `packages/prompt-library/src/index.ts`**

```typescript
// Versioned prompt templates — populated in M12-F02 (prompt versioning session).
export const PROMPT_LIBRARY_VERSION = "0.1.0";
```

- [ ] **Step 3: Create `packages/prompt-library/prompts/.gitkeep`**

Create an empty file at `packages/prompt-library/prompts/.gitkeep`.

- [ ] **Step 4: Commit**

```bash
git add packages/prompt-library/
git commit -m "[TASK-000] feat: add prompt-library package skeleton"
```

---

## Task 4: apps/candidate-web (Next.js shell)

**Files:**
- Create: `apps/candidate-web/package.json`
- Create: `apps/candidate-web/tsconfig.json`
- Create: `apps/candidate-web/next.config.ts`
- Create: `apps/candidate-web/tailwind.config.ts`
- Create: `apps/candidate-web/postcss.config.js`
- Create: `apps/candidate-web/src/app/globals.css`
- Create: `apps/candidate-web/src/app/layout.tsx`
- Create: `apps/candidate-web/src/app/page.tsx`

**Interfaces:**
- Consumes: `@arap/shared-types` via workspace
- Produces: Next.js app bootable on port 3000, `next build` exits 0

- [ ] **Step 1: Create `apps/candidate-web/package.json`**

```json
{
  "name": "candidate-web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3000",
    "build": "next build",
    "start": "next start -p 3000",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.2.5",
    "react": "^18",
    "react-dom": "^18",
    "@arap/shared-types": "workspace:*"
  },
  "devDependencies": {
    "typescript": "^5",
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "autoprefixer": "^10",
    "postcss": "^8",
    "tailwindcss": "^3",
    "eslint": "^8",
    "eslint-config-next": "14.2.5"
  }
}
```

- [ ] **Step 2: Create `apps/candidate-web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create `apps/candidate-web/next.config.ts`**

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
```

- [ ] **Step 4: Create `apps/candidate-web/tailwind.config.ts`**

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 5: Create `apps/candidate-web/postcss.config.js`**

```js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 6: Create `apps/candidate-web/src/app/globals.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --background: #ffffff;
  --foreground: #0f172a;
}

body {
  background: var(--background);
  color: var(--foreground);
  font-family: Inter, ui-sans-serif, system-ui, sans-serif;
}
```

- [ ] **Step 7: Create `apps/candidate-web/src/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ARAP — Candidate Assessment",
  description: "AI Recruitment Assessment Platform — Candidate Portal",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 8: Create `apps/candidate-web/src/app/page.tsx`**

```tsx
export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6">
      <div className="max-w-md w-full text-center space-y-6">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
          ARAP Candidate Portal
        </h1>
        <p className="text-slate-500 text-lg">
          Your assessment link will be emailed to you.
        </p>
        <button
          disabled
          className="w-full rounded-lg bg-slate-900 px-6 py-3 text-white font-medium
                     opacity-40 cursor-not-allowed"
        >
          Access Assessment
        </button>
      </div>
    </main>
  );
}
```

- [ ] **Step 9: Install dependencies and verify build**

Run from repo root:
```bash
pnpm install
pnpm --filter candidate-web build
```
Expected: `✓ Compiled successfully` — no TypeScript or build errors.

- [ ] **Step 10: Commit**

```bash
git add apps/candidate-web/
git commit -m "[TASK-000] feat: add candidate-web Next.js shell"
```

---

## Task 5: apps/console-web (Next.js shell)

**Files:**
- Create: `apps/console-web/package.json`
- Create: `apps/console-web/tsconfig.json`
- Create: `apps/console-web/next.config.ts`
- Create: `apps/console-web/tailwind.config.ts`
- Create: `apps/console-web/postcss.config.js`
- Create: `apps/console-web/src/app/globals.css`
- Create: `apps/console-web/src/app/layout.tsx`
- Create: `apps/console-web/src/app/page.tsx`
- Create: `apps/console-web/src/components/Sidebar.tsx`
- Create: `apps/console-web/src/components/Topbar.tsx`

**Interfaces:**
- Consumes: `@arap/shared-types` via workspace
- Produces: Next.js app bootable on port 3002, `next build` exits 0

- [ ] **Step 1: Create `apps/console-web/package.json`**

```json
{
  "name": "console-web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3002",
    "build": "next build",
    "start": "next start -p 3002",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.2.5",
    "react": "^18",
    "react-dom": "^18",
    "@arap/shared-types": "workspace:*"
  },
  "devDependencies": {
    "typescript": "^5",
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "autoprefixer": "^10",
    "postcss": "^8",
    "tailwindcss": "^3",
    "eslint": "^8",
    "eslint-config-next": "14.2.5"
  }
}
```

- [ ] **Step 2: Create `apps/console-web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create `apps/console-web/next.config.ts`**

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
```

- [ ] **Step 4: Create `apps/console-web/tailwind.config.ts`**

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui"],
      },
      fontSize: {
        xs: ["0.7rem", { lineHeight: "1rem" }],
        sm: ["0.8rem", { lineHeight: "1.25rem" }],
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 5: Create `apps/console-web/postcss.config.js`**

```js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 6: Create `apps/console-web/src/app/globals.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --background: #f8fafc;
  --foreground: #0f172a;
  --sidebar-bg: #1e293b;
  --sidebar-text: #cbd5e1;
}

body {
  background: var(--background);
  color: var(--foreground);
  font-family: Inter, ui-sans-serif, system-ui, sans-serif;
  font-size: 0.8rem;
}
```

- [ ] **Step 7: Create `apps/console-web/src/components/Sidebar.tsx`**

```tsx
const navItems = [
  { label: "Dashboard", href: "/" },
  { label: "Assessments", href: "/assessments" },
  { label: "Candidates", href: "/candidates" },
  { label: "Reports", href: "/reports" },
  { label: "Settings", href: "/settings" },
];

export function Sidebar() {
  return (
    <aside className="flex flex-col w-56 min-h-screen bg-slate-800 text-slate-300 shrink-0">
      <div className="px-4 py-5 border-b border-slate-700">
        <span className="text-white font-semibold text-sm tracking-wide">
          ARAP Console
        </span>
      </div>
      <nav className="flex-1 px-2 py-4 space-y-1">
        {navItems.map((item) => (
          <a
            key={item.href}
            href={item.href}
            className="flex items-center px-3 py-2 rounded-md text-sm
                       text-slate-300 hover:bg-slate-700 hover:text-white
                       transition-colors"
          >
            {item.label}
          </a>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 8: Create `apps/console-web/src/components/Topbar.tsx`**

```tsx
export function Topbar() {
  return (
    <header className="h-12 flex items-center justify-between px-6
                       bg-white border-b border-slate-200 shrink-0">
      <span className="text-sm font-medium text-slate-600">Dashboard</span>
      <div className="flex items-center gap-4">
        <span className="text-xs text-slate-400">Admin</span>
        <div className="w-7 h-7 rounded-full bg-slate-200" />
      </div>
    </header>
  );
}
```

- [ ] **Step 9: Create `apps/console-web/src/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import "./globals.css";

export const metadata: Metadata = {
  title: "ARAP Console",
  description: "AI Recruitment Assessment Platform — HR/Admin Console",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="flex min-h-screen bg-slate-50 text-slate-900 antialiased">
        <Sidebar />
        <div className="flex flex-col flex-1 min-w-0">
          <Topbar />
          <main className="flex-1 p-6 overflow-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}
```

- [ ] **Step 10: Create `apps/console-web/src/app/page.tsx`**

```tsx
const stats = [
  { label: "Active Assessments", value: "—" },
  { label: "Candidates", value: "—" },
  { label: "Reports Generated", value: "—" },
  { label: "Avg. Verdict Time", value: "—" },
];

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-800">Dashboard</h1>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="bg-white rounded-lg border border-slate-200 p-4 space-y-1"
          >
            <p className="text-xs text-slate-500">{stat.label}</p>
            <p className="text-2xl font-semibold text-slate-800">{stat.value}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-slate-400">
        Console shell — features coming in Phase 1.
      </p>
    </div>
  );
}
```

- [ ] **Step 11: Verify build**

Run from repo root:
```bash
pnpm --filter console-web build
```
Expected: `✓ Compiled successfully` — no TypeScript or build errors.

- [ ] **Step 12: Commit**

```bash
git add apps/console-web/
git commit -m "[TASK-000] feat: add console-web Next.js shell"
```

---

## Task 6: FastAPI Bootstrap

**Files:**
- Modify: `services/orchestrator-api/pyproject.toml`
- Create: `services/orchestrator-api/src/config.py`
- Create: `services/orchestrator-api/src/main.py`
- Create: `services/orchestrator-api/src/middleware/__init__.py`
- Create: `services/orchestrator-api/src/middleware/auth.py`
- Create: `services/orchestrator-api/src/middleware/rbac.py`
- Create: `services/orchestrator-api/src/middleware/rate_limit.py`
- Create: `services/orchestrator-api/src/middleware/error_handler.py`
- Create: `services/orchestrator-api/src/api/__init__.py`
- Create: `services/orchestrator-api/src/api/health.py`
- Create: `services/orchestrator-api/tests/api/__init__.py`
- Create: `services/orchestrator-api/tests/api/test_health.py`

**Interfaces:**
- Produces: `app` (FastAPI instance) importable as `from src.main import app`
- Produces: `GET /health` → `{"status": "ok", "version": str}`
- Produces: `Settings` importable as `from src.config import settings`

- [ ] **Step 1: Update `services/orchestrator-api/pyproject.toml`**

Replace the existing content with:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "orchestrator-api"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "pgvector>=0.3",
    "psycopg2-binary>=2.9",
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "pydantic-settings>=2.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-env>=1.1",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
env = [
    "TEST_DATABASE_URL=postgresql://arap:arap@localhost:5434/arap_test",
    "DATABASE_URL=postgresql://arap:arap@localhost:5433/arap_dev",
    "SECRET_KEY=test-secret-key-not-for-production",
]
```

- [ ] **Step 2: Write the failing test first**

Create `services/orchestrator-api/tests/api/__init__.py` (empty file).

Create `services/orchestrator-api/tests/api/test_health.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.anyio
async def test_health_returns_ok():
    from src.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


@pytest.mark.anyio
async def test_health_version_matches_config():
    from src.main import app
    from src.config import settings

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.json()["version"] == settings.APP_VERSION
```

- [ ] **Step 3: Run the failing tests** (from `services/orchestrator-api/`)

```bash
pip install -e ".[dev]"
pytest tests/api/test_health.py -v
```
Expected: `ERROR` — `ModuleNotFoundError: No module named 'src.main'`

- [ ] **Step 4: Create `services/orchestrator-api/src/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql://arap:arap@localhost:5433/arap_dev"
    SECRET_KEY: str = "change-me-in-production"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "info"
    APP_VERSION: str = "0.1.0"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3002"]


settings = Settings()
```

- [ ] **Step 5: Create `services/orchestrator-api/src/middleware/__init__.py`** (empty file)

- [ ] **Step 6: Create `services/orchestrator-api/src/middleware/auth.py`**

```python
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Stub — auth logic added in auth session."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not request.headers.get("Authorization"):
            logger.debug("Request without Authorization header: %s", request.url.path)
        return await call_next(request)
```

- [ ] **Step 7: Create `services/orchestrator-api/src/middleware/rbac.py`**

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RBACMiddleware(BaseHTTPMiddleware):
    """Stub — role extraction and enforcement added in auth session."""

    async def dispatch(self, request: Request, call_next) -> Response:
        return await call_next(request)
```

- [ ] **Step 8: Create `services/orchestrator-api/src/middleware/rate_limit.py`**

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Stub — token-bucket rate limiting added post-Phase 0."""

    async def dispatch(self, request: Request, call_next) -> Response:
        return await call_next(request)
```

- [ ] **Step 9: Create `services/orchestrator-api/src/middleware/error_handler.py`**

```python
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException

logger = logging.getLogger(__name__)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "status_code": 500},
    )
```

- [ ] **Step 10: Create `services/orchestrator-api/src/api/__init__.py`** (empty file)

- [ ] **Step 11: Create `services/orchestrator-api/src/api/health.py`**

```python
from fastapi import APIRouter
from src.config import settings

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": settings.APP_VERSION}
```

- [ ] **Step 12: Create `services/orchestrator-api/src/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException

from src.config import settings
from src.middleware.auth import AuthMiddleware
from src.middleware.rbac import RBACMiddleware
from src.middleware.rate_limit import RateLimitMiddleware
from src.middleware.error_handler import http_exception_handler, unhandled_exception_handler
from src.api.health import router as health_router

app = FastAPI(
    title="ARAP Orchestrator API",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RBACMiddleware)
app.add_middleware(AuthMiddleware)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(health_router)
```

- [ ] **Step 13: Add anyio pytest marker**

`httpx` async tests need `anyio`. Add to `pyproject.toml` dev deps and pytest config:

In `pyproject.toml`, add `"anyio[asyncio]>=4.0"` and `"pytest-anyio>=0.0.0"` to dev deps — actually use `anyio` test mode via marker. Update `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
env = [
    "TEST_DATABASE_URL=postgresql://arap:arap@localhost:5434/arap_test",
    "DATABASE_URL=postgresql://arap:arap@localhost:5433/arap_dev",
    "SECRET_KEY=test-secret-key-not-for-production",
]
```

And add to dev deps: `"anyio[asyncio]>=4.0"`, `"pytest-asyncio>=0.23"`.

Update the test file to use `pytest.mark.asyncio` instead of `anyio`:

Replace `tests/api/test_health.py` with:

```python
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health_returns_ok():
    from src.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


@pytest.mark.asyncio
async def test_health_version_matches_config():
    from src.main import app
    from src.config import settings

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.json()["version"] == settings.APP_VERSION
```

- [ ] **Step 14: Run all tests** (from `services/orchestrator-api/`)

```bash
pip install -e ".[dev]"
pytest -v
```
Expected: all 44 existing tests PASS + 2 new health tests PASS = 46 tests green.

If the existing model tests fail because DB is not running, start Docker first:
```bash
docker compose up -d
```
Then re-run.

- [ ] **Step 15: Smoke-test uvicorn** (from `services/orchestrator-api/`)

```bash
uvicorn src.main:app --reload
```
In a second terminal:
```bash
curl http://localhost:8000/health
```
Expected: `{"status":"ok","version":"0.1.0"}`

Stop uvicorn (Ctrl+C).

- [ ] **Step 16: Commit**

```bash
git add services/orchestrator-api/
git commit -m "[TASK-000] feat: FastAPI bootstrap — config, middleware stubs, health endpoint"
```

---

## Task 7: services/realtime-gateway skeleton

**Files:**
- Create: `services/realtime-gateway/package.json`
- Create: `services/realtime-gateway/src/index.js`

**Interfaces:**
- Produces: HTTP server on `PORT` env var (default 3001) responding `{"status":"ok"}` on `GET /health`

- [ ] **Step 1: Create `services/realtime-gateway/package.json`**

```json
{
  "name": "realtime-gateway",
  "version": "0.1.0",
  "private": true,
  "main": "src/index.js",
  "engines": { "node": ">=20" },
  "scripts": {
    "start": "node src/index.js",
    "dev": "node --watch src/index.js"
  }
}
```

- [ ] **Step 2: Create `services/realtime-gateway/src/index.js`**

```js
const http = require("http");

const PORT = process.env.PORT ?? 3001;

const server = http.createServer((req, res) => {
  if (req.method === "GET" && req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok", service: "realtime-gateway" }));
    return;
  }
  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ error: "not found" }));
});

server.listen(PORT, () => {
  console.log(`realtime-gateway listening on port ${PORT}`);
});
```

- [ ] **Step 3: Verify it starts**

```bash
node services/realtime-gateway/src/index.js
```
Expected output: `realtime-gateway listening on port 3001`

Stop with Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add services/realtime-gateway/
git commit -m "[TASK-000] feat: realtime-gateway Node.js skeleton"
```

---

## Task 8: services/ingestion-service skeleton

**Files:**
- Create: `services/ingestion-service/pyproject.toml`
- Create: `services/ingestion-service/src/__init__.py`
- Create: `services/ingestion-service/src/main.py`
- Create: `services/ingestion-service/tests/__init__.py`

**Interfaces:**
- Produces: installable Python package `ingestion-service`; FastAPI `GET /health` stub

- [ ] **Step 1: Create `services/ingestion-service/pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "ingestion-service"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `services/ingestion-service/src/__init__.py`** (empty file)

- [ ] **Step 3: Create `services/ingestion-service/src/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="ARAP Ingestion Service", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "ingestion-service"}
```

- [ ] **Step 4: Create `services/ingestion-service/tests/__init__.py`** (empty file)

- [ ] **Step 5: Verify install**

```bash
pip install -e services/ingestion-service/
```
Expected: installs without errors.

- [ ] **Step 6: Commit**

```bash
git add services/ingestion-service/
git commit -m "[TASK-000] feat: ingestion-service Python skeleton"
```

---

## Task 9: Agent skeletons (8 folders)

**Files:**
- Create: `agents/{name}/__init__.py` and `agents/{name}/README.md` for each of 8 agents

**Interfaces:**
- Produces: importable Python packages for all 8 agents; no logic

The 8 agents and their PRD refs:

| Folder | PRD ref |
|---|---|
| `resume_analysis` | §7, M2/M3 |
| `job_description` | §7, M1 |
| `question_generation` | §7, M4 |
| `evaluation` | §7, M6 |
| `behavior_analysis` | §7, M7 |
| `scoring` | §7, M6/M9 |
| `recommendation` | §7, M9 |
| `report_generator` | §7, M9 |

- [ ] **Step 1: Create all agent `__init__.py` files** (all empty)

Create these 8 files (each empty):
```
agents/resume_analysis/__init__.py
agents/job_description/__init__.py
agents/question_generation/__init__.py
agents/evaluation/__init__.py
agents/behavior_analysis/__init__.py
agents/scoring/__init__.py
agents/recommendation/__init__.py
agents/report_generator/__init__.py
```

- [ ] **Step 2: Create `agents/resume_analysis/README.md`**

```markdown
# resume_analysis agent

Parses candidate resume, LinkedIn, and GitHub data into a structured candidate profile.

**PRD ref:** §7, M2-F01–F04, M3
**Status:** Skeleton — implemented in Phase 1
```

- [ ] **Step 3: Create `agents/job_description/README.md`**

```markdown
# job_description agent

Processes HR job assessment input into a structured `job_profile` used by downstream agents.

**PRD ref:** §7, M1
**Status:** Skeleton — implemented in Phase 1
```

- [ ] **Step 4: Create `agents/question_generation/README.md`**

```markdown
# question_generation agent

Generates a personalized, locked question set from `job_profile` + `candidate_profile`.

**PRD ref:** §7, M4-F01–F06
**Status:** Skeleton — implemented in Phase 1
```

- [ ] **Step 5: Create `agents/evaluation/README.md`**

```markdown
# evaluation agent

Scores every submitted candidate answer against the multi-competency rubric.

**PRD ref:** §7, M6
**Status:** Skeleton — implemented in Phase 1
```

- [ ] **Step 6: Create `agents/behavior_analysis/README.md`**

```markdown
# behavior_analysis agent

Infers DISC, Big Five, leadership style, and EQ from the candidate's answer set.

**PRD ref:** §7, M7
**Status:** Skeleton — implemented in Phase 2
```

- [ ] **Step 7: Create `agents/scoring/README.md`**

```markdown
# scoring agent

Aggregates per-answer scores and behavior profile into a unified score rollup.

**PRD ref:** §7, M6/M9 scoring pipeline
**Status:** Skeleton — implemented in Phase 1
```

- [ ] **Step 8: Create `agents/recommendation/README.md`**

```markdown
# recommendation agent

Produces a hiring recommendation block (Strong Hire / Hire / Consider / Borderline / Reject).

**PRD ref:** §7, M9-F01
**Status:** Skeleton — implemented in Phase 1
```

- [ ] **Step 9: Create `agents/report_generator/README.md`**

```markdown
# report_generator agent

Assembles the final, explainable hiring report from all upstream agent outputs.

**PRD ref:** §7, M9
**Status:** Skeleton — implemented in Phase 1
```

- [ ] **Step 10: Commit**

```bash
git add agents/
git commit -m "[TASK-000] feat: add 8 agent skeleton folders"
```

---

## Task 10: infra/ placeholders

**Files:**
- Create: `infra/docker/.gitkeep`
- Create: `infra/terraform/.gitkeep`

- [ ] **Step 1: Create placeholder files**

Create empty files at:
- `infra/docker/.gitkeep`
- `infra/terraform/.gitkeep`

- [ ] **Step 2: Commit**

```bash
git add infra/
git commit -m "[TASK-000] chore: add infra/ placeholder directories"
```

---

## Task 11: Root docker-compose.yml + .env.example

**Files:**
- Create: `docker-compose.yml` (repo root)
- Create: `.env.example` (repo root)

**Interfaces:**
- Produces: `docker compose up -d` starts `db-dev` (port 5433) and `db-test` (port 5434)
- The existing `services/orchestrator-api/docker-compose.yml` is kept as-is (used by local pytest)

- [ ] **Step 1: Create root `docker-compose.yml`**

```yaml
version: "3.9"

services:
  db-dev:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: arap
      POSTGRES_PASSWORD: arap
      POSTGRES_DB: arap_dev
    ports:
      - "5433:5432"
    volumes:
      - pgdata-dev:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U arap -d arap_dev"]
      interval: 5s
      timeout: 5s
      retries: 5

  db-test:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: arap
      POSTGRES_PASSWORD: arap
      POSTGRES_DB: arap_test
    ports:
      - "5434:5432"
    volumes:
      - pgdata-test:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U arap -d arap_test"]
      interval: 5s
      timeout: 5s
      retries: 5

  orchestrator-api:
    build:
      context: services/orchestrator-api
      dockerfile: ../../infra/docker/orchestrator-api.Dockerfile
    environment:
      DATABASE_URL: postgresql://arap:arap@db-dev:5432/arap_dev
      SECRET_KEY: ${SECRET_KEY:-change-me}
      ENVIRONMENT: ${ENVIRONMENT:-development}
    ports:
      - "8000:8000"
    depends_on:
      db-dev:
        condition: service_healthy
    profiles:
      - full

  realtime-gateway:
    build:
      context: services/realtime-gateway
      dockerfile: ../../infra/docker/realtime-gateway.Dockerfile
    environment:
      PORT: 3001
    ports:
      - "3001:3001"
    profiles:
      - full

volumes:
  pgdata-dev:
  pgdata-test:
```

Note: `orchestrator-api` and `realtime-gateway` services use `profiles: [full]` — they require Dockerfiles in `infra/docker/` which are not built yet. Run `docker compose up -d` (without `--profile full`) to start only the DB containers, which is all Phase 0 needs.

- [ ] **Step 2: Verify DB containers start**

```bash
docker compose up -d
docker compose ps
```
Expected: `db-dev` and `db-test` containers show `running (healthy)`.

- [ ] **Step 3: Create `.env.example`**

```dotenv
# ── Database ──────────────────────────────────────────────
DATABASE_URL=postgresql://arap:arap@localhost:5433/arap_dev
TEST_DATABASE_URL=postgresql://arap:arap@localhost:5434/arap_test

# ── API ───────────────────────────────────────────────────
SECRET_KEY=change-me-in-production
ENVIRONMENT=development
LOG_LEVEL=info
APP_VERSION=0.1.0

# ── CORS / Frontend ───────────────────────────────────────
NEXT_PUBLIC_API_URL=http://localhost:8000

# ── Real-time Gateway ─────────────────────────────────────
PORT=3001
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "[TASK-000] chore: root docker-compose and .env.example"
```

---

## Task 12: CI Pipeline

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: GitHub Actions workflow that runs `lint`, `test`, `build` jobs on push/PR to `main`
- `test` is blocked by `lint`; `build` runs in parallel with `test`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Ruff
        run: pip install ruff>=0.4

      - name: Lint Python
        run: |
          ruff check services/orchestrator-api/src \
                       services/ingestion-service/src \
                       agents/

      - name: Set up pnpm
        uses: pnpm/action-setup@v3
        with:
          version: 9

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "pnpm"

      - name: Install JS deps
        run: pnpm install --frozen-lockfile

      - name: Lint JS
        run: pnpm --filter "./apps/*" lint

  test:
    name: Test
    runs-on: ubuntu-latest
    needs: lint

    services:
      db-test:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: arap
          POSTGRES_PASSWORD: arap
          POSTGRES_DB: arap_test
        ports:
          - 5434:5432
        options: >-
          --health-cmd "pg_isready -U arap -d arap_test"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install orchestrator-api
        working-directory: services/orchestrator-api
        run: pip install -e ".[dev]"

      - name: Run pytest
        working-directory: services/orchestrator-api
        env:
          TEST_DATABASE_URL: postgresql://arap:arap@localhost:5434/arap_test
          DATABASE_URL: postgresql://arap:arap@localhost:5434/arap_test
          SECRET_KEY: ci-test-secret
        run: pytest -v

  build:
    name: Build
    runs-on: ubuntu-latest
    needs: lint

    steps:
      - uses: actions/checkout@v4

      - name: Set up pnpm
        uses: pnpm/action-setup@v3
        with:
          version: 9

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "pnpm"

      - name: Install JS deps
        run: pnpm install --frozen-lockfile

      - name: Build candidate-web
        run: pnpm --filter candidate-web build

      - name: Build console-web
        run: pnpm --filter console-web build

      - name: Smoke-install Python services
        run: |
          pip install -e services/orchestrator-api/
          pip install -e services/ingestion-service/
```

- [ ] **Step 2: Commit**

```bash
git add .github/
git commit -m "[TASK-000] ci: add GitHub Actions lint, test, build pipeline"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| Full monorepo layout per PRD §11.2 | Tasks 1–10 |
| pnpm workspaces | Task 1 |
| FastAPI bootstrap: config, middleware stubs, health | Task 6 |
| candidate-web Next.js shell (minimal) | Task 4 |
| console-web Next.js shell (dense) | Task 5 |
| shared-types package | Task 2 |
| prompt-library package | Task 3 |
| realtime-gateway Node.js skeleton | Task 7 |
| ingestion-service Python skeleton | Task 8 |
| 8 agent skeletons | Task 9 |
| infra/docker, infra/terraform placeholders | Task 10 |
| Root docker-compose.yml | Task 11 |
| .env.example | Task 11 |
| GitHub Actions CI (lint + test + build) | Task 12 |
| Existing 44 tests still pass | Verified in Task 6 step 14 |
| Port conflict resolved (candidate 3000, gateway 3001, console 3002) | Tasks 4, 5, 7 |

**No gaps found.**

**Placeholder scan:** No TBD/TODO in any code block. All steps have complete code.

**Type consistency:** `settings.APP_VERSION` used consistently in `health.py`, `main.py`, and both test assertions.

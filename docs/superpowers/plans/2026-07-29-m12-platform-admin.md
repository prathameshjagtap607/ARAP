# M12 Platform Administration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Super Admin layer for tenant management, versioned prompt library with rollback, per-agent model routing (hot-swappable via Redis), and system health monitoring.

**Architecture:** Single `src/modules/admin/` module with four sub-modules (tenants, prompts, routing, health), all gated by a new `require_super_admin` dependency. One Alembic migration (0007) adds the `super_admin` role, extends `orgs`, creates `model_routing_configs`, and adds `prompt_template_id` traceability to `assessment_sessions`. Model routing reads from Postgres, caches in Redis with a 30s TTL, and invalidates immediately on PATCH.

**Tech Stack:** FastAPI, SQLAlchemy 2.x (sync), Alembic, PostgreSQL, Redis (via `get_redis()`), fakeredis (tests), pytest-asyncio, httpx AsyncClient, Next.js 14 App Router, Tailwind CSS.

## Global Constraints

- Python files: follow `src/modules/analytics/` pattern exactly — sync endpoints, `sqlalchemy.text()` for all queries, Pydantic v2 `BaseModel`
- All `/admin/*` routes require `require_super_admin` — no exceptions
- Migration numbering: `0007` (revises `0006`)
- Test DB: `postgresql://arap:arap@localhost:5434/arap_test` — real DB, no DB mocks
- Redis mock in tests: `fakeredis.FakeRedis(decode_responses=True)` — no real Redis in tests
- Frontend: `"use client"`, `useEffect` + `AbortController` pattern from analytics components
- All commit messages prefixed `feat(admin):` or `test(admin):`

---

## File Map

**New files — backend:**
```
services/orchestrator-api/migrations/versions/0007_platform_admin.py
services/orchestrator-api/src/models/model_routing_configs.py
services/orchestrator-api/src/modules/admin/__init__.py
services/orchestrator-api/src/modules/admin/router.py
services/orchestrator-api/src/modules/admin/tenants/__init__.py
services/orchestrator-api/src/modules/admin/tenants/schemas.py
services/orchestrator-api/src/modules/admin/tenants/service.py
services/orchestrator-api/src/modules/admin/tenants/router.py
services/orchestrator-api/src/modules/admin/prompts/__init__.py
services/orchestrator-api/src/modules/admin/prompts/schemas.py
services/orchestrator-api/src/modules/admin/prompts/service.py
services/orchestrator-api/src/modules/admin/prompts/router.py
services/orchestrator-api/src/modules/admin/routing/__init__.py
services/orchestrator-api/src/modules/admin/routing/schemas.py
services/orchestrator-api/src/modules/admin/routing/service.py
services/orchestrator-api/src/modules/admin/routing/router.py
services/orchestrator-api/src/modules/admin/health/__init__.py
services/orchestrator-api/src/modules/admin/health/schemas.py
services/orchestrator-api/src/modules/admin/health/service.py
services/orchestrator-api/src/modules/admin/health/router.py
tests/admin/__init__.py
tests/admin/conftest.py
tests/admin/test_tenants.py
tests/admin/test_prompts.py
tests/admin/test_routing.py
tests/admin/test_health.py
```

**Modified — backend:**
```
services/orchestrator-api/src/models/__init__.py          — add ModelRoutingConfig
services/orchestrator-api/src/models/orgs.py              — add workspace_limit, is_active, suspended_at
services/orchestrator-api/src/models/assessment_sessions.py — add prompt_template_id FK
services/orchestrator-api/src/modules/auth/dependencies.py  — add require_super_admin
services/orchestrator-api/src/main.py                     — include admin_router
```

**New files — frontend:**
```
apps/console-web/src/app/(console)/admin/page.tsx
apps/console-web/src/app/(console)/admin/_components/TenantsTab.tsx
apps/console-web/src/app/(console)/admin/_components/PromptsTab.tsx
apps/console-web/src/app/(console)/admin/_components/RoutingTab.tsx
apps/console-web/src/app/(console)/admin/_components/HealthTab.tsx
apps/console-web/src/app/(console)/admin/_lib/api.ts
apps/console-web/src/app/(console)/admin/_lib/types.ts
```

**Modified — packages:**
```
packages/prompt-library/src/index.ts                      — add AGENT_NAMES, PromptVersion, ModelRoutingConfig types
```

---

### Task 1: Alembic Migration 0007 + Model Updates

**Files:**
- Create: `services/orchestrator-api/migrations/versions/0007_platform_admin.py`
- Create: `services/orchestrator-api/src/models/model_routing_configs.py`
- Modify: `services/orchestrator-api/src/models/orgs.py`
- Modify: `services/orchestrator-api/src/models/assessment_sessions.py`
- Modify: `services/orchestrator-api/src/models/__init__.py`

**Interfaces:**
- Produces: `ModelRoutingConfig` ORM model with fields `id, agent_name, provider, model_id, fallback_provider, fallback_model_id, is_active, updated_by, updated_at`
- Produces: `Org` model extended with `workspace_limit: int`, `is_active: bool`, `suspended_at: datetime | None`
- Produces: `AssessmentSession` model extended with `prompt_template_id: uuid.UUID | None`

- [ ] **Step 1: Update `src/models/orgs.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    plan_tier: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("'trial'")
    )
    workspace_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("5")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 2: Check what `assessment_sessions.py` looks like, then add `prompt_template_id`**

Read `services/orchestrator-api/src/models/assessment_sessions.py` first. Then add:

```python
    prompt_template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("prompt_templates.id"), nullable=True
    )
```

as the last column before any relationships.

- [ ] **Step 3: Create `src/models/model_routing_configs.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ModelRoutingConfig(Base):
    __tablename__ = "model_routing_configs"
    __table_args__ = (
        UniqueConstraint("agent_name", name="uq_routing_agent"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    agent_name: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    fallback_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    fallback_model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4: Register `ModelRoutingConfig` in `src/models/__init__.py`**

Add to imports and `__all__`:
```python
from .model_routing_configs import ModelRoutingConfig
# in __all__: "ModelRoutingConfig",
```

- [ ] **Step 5: Write the Alembic migration**

Create `migrations/versions/0007_platform_admin.py`:

```python
"""platform admin: role constraint, orgs extensions, model_routing_configs, session traceability

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-29
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Expand role check constraint to include super_admin
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('user', 'admin', 'super_admin')",
    )

    # 2. Extend orgs
    op.add_column("orgs", sa.Column("workspace_limit", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("orgs", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("orgs", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))

    # 3. Add prompt traceability to assessment_sessions
    op.add_column(
        "assessment_sessions",
        sa.Column("prompt_template_id", UUID(), sa.ForeignKey("prompt_templates.id"), nullable=True),
    )

    # 4. Create model_routing_configs
    op.create_table(
        "model_routing_configs",
        sa.Column("id", UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("fallback_provider", sa.String(), nullable=True),
        sa.Column("fallback_model_id", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_by", UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("agent_name", name="uq_routing_agent"),
    )

    # 5. Seed default routing config for the three known agents
    op.execute(sa.text("""
        INSERT INTO model_routing_configs (agent_name, provider, model_id)
        VALUES
          ('question_generator', 'anthropic', 'claude-sonnet-5'),
          ('report_writer',      'anthropic', 'claude-sonnet-5'),
          ('scorer',             'anthropic', 'claude-haiku-4-5-20251001')
    """))


def downgrade() -> None:
    op.drop_table("model_routing_configs")
    op.drop_column("assessment_sessions", "prompt_template_id")
    op.drop_column("orgs", "suspended_at")
    op.drop_column("orgs", "is_active")
    op.drop_column("orgs", "workspace_limit")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role", "users", "role IN ('user', 'admin')"
    )
```

- [ ] **Step 6: Apply migration to dev DB**

```bash
cd services/orchestrator-api
alembic upgrade head
```

Expected: `Running upgrade 0006 -> 0007, platform admin...`

- [ ] **Step 7: Smoke-test schema**

```bash
psql postgresql://arap:arap@localhost:5433/arap_dev -c "\d model_routing_configs"
psql postgresql://arap:arap@localhost:5433/arap_dev -c "SELECT agent_name, provider, model_id FROM model_routing_configs;"
```

Expected: three rows seeded.

- [ ] **Step 8: Commit**

```bash
git add migrations/versions/0007_platform_admin.py \
        src/models/model_routing_configs.py \
        src/models/orgs.py \
        src/models/assessment_sessions.py \
        src/models/__init__.py
git commit -m "feat(admin): migration 0007 — role, orgs, model_routing_configs, session traceability"
```

---

### Task 2: `require_super_admin` + Admin Module Scaffold + main.py

**Files:**
- Modify: `services/orchestrator-api/src/modules/auth/dependencies.py`
- Create: `services/orchestrator-api/src/modules/admin/__init__.py`
- Create: `services/orchestrator-api/src/modules/admin/router.py`
- Create: all four sub-module `__init__.py` stubs
- Modify: `services/orchestrator-api/src/main.py`
- Create: `services/orchestrator-api/tests/admin/__init__.py`
- Create: `services/orchestrator-api/tests/admin/conftest.py`

**Interfaces:**
- Produces: `require_super_admin(claims: TokenClaims = Depends(get_claims)) -> TokenClaims` — raises 403 if `role != "super_admin"`
- Produces: `admin_router` mounted at `/admin`
- Produces: `conftest.py` with `super_admin_token` fixture and `admin_seed` fixture

- [ ] **Step 1: Write test for `require_super_admin` — verify it blocks non-super-admin**

Create `tests/admin/conftest.py`:

```python
import os
import uuid as _uuid

import fakeredis
import pytest
import pytest_asyncio
import src.models  # noqa: F401
from httpx import ASGITransport, AsyncClient
from passlib.context import CryptContext
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.models.base import Base
from src.models.orgs import Org
from src.models.users import User
from src.modules.auth.token import create_access_token

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://arap:arap@localhost:5434/arap_test"
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL)
    with eng.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    _Session = sessionmaker(engine)
    s = _Session()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def admin_seed(db: Session) -> dict:
    uid = _uuid.uuid4().hex[:8]
    system_org = Org(name=f"System Org {uid}")
    tenant_org = Org(name=f"Tenant Org {uid}")
    db.add_all([system_org, tenant_org])
    db.flush()

    super_admin = User(
        org_id=system_org.id,
        email=f"superadmin-{uid}@system.com",
        role="super_admin",
        password_hash=pwd_context.hash("x"),
    )
    regular_admin = User(
        org_id=tenant_org.id,
        email=f"admin-{uid}@tenant.com",
        role="admin",
        password_hash=pwd_context.hash("x"),
    )
    db.add_all([super_admin, regular_admin])
    db.flush()
    db.commit()
    return {
        "system_org": system_org,
        "tenant_org": tenant_org,
        "super_admin": super_admin,
        "regular_admin": regular_admin,
    }


@pytest.fixture
def super_admin_token(admin_seed: dict) -> str:
    return create_access_token({
        "sub": str(admin_seed["super_admin"].id),
        "role": "super_admin",
        "org_id": str(admin_seed["system_org"].id),
    })


@pytest.fixture
def admin_token(admin_seed: dict) -> str:
    return create_access_token({
        "sub": str(admin_seed["regular_admin"].id),
        "role": "admin",
        "org_id": str(admin_seed["tenant_org"].id),
    })


@pytest_asyncio.fixture
async def async_client(db: Session, r):
    from src.database import get_db, get_redis
    from src.main import app

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: r
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()
```

Create `tests/admin/__init__.py` (empty).

- [ ] **Step 2: Write the scaffold test**

Create `tests/admin/test_tenants.py` with a placeholder test (will be expanded in Task 3):

```python
import pytest

@pytest.mark.asyncio
class TestSuperAdminGuard:
    async def test_admin_cannot_access_tenants(self, async_client, admin_seed, admin_token):
        resp = await async_client.get(
            "/admin/tenants",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_access_tenants(self, async_client):
        resp = await async_client.get("/admin/tenants")
        assert resp.status_code == 401
```

- [ ] **Step 3: Run tests — expect FAIL (router not yet wired)**

```bash
cd services/orchestrator-api
pytest tests/admin/test_tenants.py -v
```

Expected: ERROR or FAIL — `/admin/tenants` returns 404 (not wired yet).

- [ ] **Step 4: Add `require_super_admin` to `auth/dependencies.py`**

Add after the `require_admin` function:

```python
def require_super_admin(claims: TokenClaims = Depends(get_claims)) -> TokenClaims:
    if claims.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return claims
```

- [ ] **Step 5: Create admin module scaffold**

`src/modules/admin/__init__.py` — empty.

`src/modules/admin/router.py`:

```python
from fastapi import APIRouter

from src.modules.admin.tenants.router import router as tenants_router
from src.modules.admin.prompts.router import router as prompts_router
from src.modules.admin.routing.router import router as routing_router
from src.modules.admin.health.router import router as health_router

router = APIRouter(prefix="/admin", tags=["admin"])

router.include_router(tenants_router)
router.include_router(prompts_router)
router.include_router(routing_router)
router.include_router(health_router)
```

Create empty `__init__.py` in all four sub-modules:
- `src/modules/admin/tenants/__init__.py`
- `src/modules/admin/prompts/__init__.py`
- `src/modules/admin/routing/__init__.py`
- `src/modules/admin/health/__init__.py`

Create stub routers for the three tasks not yet implemented (needed so admin/router.py imports don't fail):

`src/modules/admin/prompts/router.py`:
```python
from fastapi import APIRouter
router = APIRouter(prefix="/prompts", tags=["admin-prompts"])
```

`src/modules/admin/routing/router.py`:
```python
from fastapi import APIRouter
router = APIRouter(prefix="/routing", tags=["admin-routing"])
```

`src/modules/admin/health/router.py`:
```python
from fastapi import APIRouter
router = APIRouter(prefix="/health", tags=["admin-health"])
```

- [ ] **Step 6: Create tenant stub router**

`src/modules/admin/tenants/router.py`:

```python
from fastapi import APIRouter, Depends
from src.modules.auth.dependencies import TokenClaims, require_super_admin

router = APIRouter(prefix="/tenants", tags=["admin-tenants"])


@router.get("")
def list_tenants(claims: TokenClaims = Depends(require_super_admin)):
    return []
```

- [ ] **Step 7: Wire admin router into `main.py`**

Add two lines to `src/main.py`:

```python
from src.modules.admin.router import router as admin_router
# ...
app.include_router(admin_router)
```

- [ ] **Step 8: Run tests — expect PASS**

```bash
pytest tests/admin/test_tenants.py::TestSuperAdminGuard -v
```

Expected: both tests PASS.

- [ ] **Step 9: Commit**

```bash
git add src/modules/auth/dependencies.py \
        src/modules/admin/ \
        src/main.py \
        tests/admin/
git commit -m "feat(admin): scaffold admin module, require_super_admin, main.py wiring"
```

---

### Task 3: F01 — Tenant & Workspace Management

**Files:**
- Create: `src/modules/admin/tenants/schemas.py`
- Create: `src/modules/admin/tenants/service.py`
- Modify: `src/modules/admin/tenants/router.py`
- Modify: `tests/admin/test_tenants.py`

**Interfaces:**
- Consumes: `require_super_admin` from Task 2; `Org` model from Task 1
- Produces:
  - `list_tenants(db) -> list[TenantDetail]`
  - `get_tenant(db, org_id) -> TenantDetail` (raises `LookupError` if not found)
  - `create_tenant(db, payload: TenantCreate) -> TenantDetail`
  - `update_tenant(db, org_id, payload: TenantUpdate) -> TenantDetail`
  - `suspend_tenant(db, org_id) -> TenantDetail`

- [ ] **Step 1: Write failing tests**

Replace `tests/admin/test_tenants.py` with full test suite:

```python
import pytest

@pytest.mark.asyncio
class TestSuperAdminGuard:
    async def test_admin_cannot_access_tenants(self, async_client, admin_token):
        resp = await async_client.get(
            "/admin/tenants",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_access_tenants(self, async_client):
        resp = await async_client.get("/admin/tenants")
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestTenantCRUD:
    async def test_list_tenants_returns_orgs(self, async_client, admin_seed, super_admin_token):
        resp = await async_client.get(
            "/admin/tenants",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        org_names = [t["name"] for t in body]
        assert admin_seed["tenant_org"].name in org_names

    async def test_create_tenant(self, async_client, super_admin_token):
        resp = await async_client.post(
            "/admin/tenants",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"name": "New Corp", "plan_tier": "pro", "workspace_limit": 10},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "New Corp"
        assert body["plan_tier"] == "pro"
        assert body["workspace_limit"] == 10
        assert body["is_active"] is True

    async def test_get_tenant(self, async_client, admin_seed, super_admin_token):
        org_id = str(admin_seed["tenant_org"].id)
        resp = await async_client.get(
            f"/admin/tenants/{org_id}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == org_id

    async def test_get_tenant_not_found(self, async_client, super_admin_token):
        import uuid
        resp = await async_client.get(
            f"/admin/tenants/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 404

    async def test_update_tenant_plan_tier(self, async_client, admin_seed, super_admin_token):
        org_id = str(admin_seed["tenant_org"].id)
        resp = await async_client.patch(
            f"/admin/tenants/{org_id}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"plan_tier": "enterprise"},
        )
        assert resp.status_code == 200
        assert resp.json()["plan_tier"] == "enterprise"

    async def test_suspend_tenant(self, async_client, admin_seed, super_admin_token):
        org_id = str(admin_seed["tenant_org"].id)
        resp = await async_client.delete(
            f"/admin/tenants/{org_id}/suspend",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_active"] is False
        assert body["suspended_at"] is not None
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/admin/test_tenants.py -v
```

Expected: failures on all CRUD tests (no service/schema yet).

- [ ] **Step 3: Create `tenants/schemas.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel


class TenantCreate(BaseModel):
    name: str
    plan_tier: str = "trial"
    workspace_limit: int = 5


class TenantUpdate(BaseModel):
    plan_tier: str | None = None
    workspace_limit: int | None = None
    is_active: bool | None = None


class TenantDetail(BaseModel):
    id: uuid.UUID
    name: str
    plan_tier: str
    workspace_limit: int
    is_active: bool
    suspended_at: datetime | None
    created_at: datetime
    user_count: int
    session_count: int

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Create `tenants/service.py`**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.modules.admin.tenants.schemas import TenantCreate, TenantDetail, TenantUpdate


def _row_to_detail(row) -> TenantDetail:
    return TenantDetail(
        id=row["id"],
        name=row["name"],
        plan_tier=row["plan_tier"],
        workspace_limit=row["workspace_limit"],
        is_active=row["is_active"],
        suspended_at=row["suspended_at"],
        created_at=row["created_at"],
        user_count=int(row["user_count"]),
        session_count=int(row["session_count"]),
    )


_TENANT_SQL = """
    SELECT
        o.id, o.name, o.plan_tier, o.workspace_limit, o.is_active,
        o.suspended_at, o.created_at,
        COUNT(DISTINCT u.id) AS user_count,
        COUNT(DISTINCT s.id) AS session_count
    FROM orgs o
    LEFT JOIN users u ON u.org_id = o.id
    LEFT JOIN assessment_sessions s ON s.org_id = o.id
"""


def list_tenants(db: Session) -> list[TenantDetail]:
    rows = db.execute(
        text(_TENANT_SQL + " GROUP BY o.id ORDER BY o.created_at DESC")
    ).mappings().all()
    return [_row_to_detail(r) for r in rows]


def get_tenant(db: Session, org_id: uuid.UUID) -> TenantDetail:
    row = db.execute(
        text(_TENANT_SQL + " WHERE o.id = :org_id GROUP BY o.id"),
        {"org_id": org_id},
    ).mappings().first()
    if not row:
        raise LookupError(f"Org {org_id} not found")
    return _row_to_detail(row)


def create_tenant(db: Session, payload: TenantCreate) -> TenantDetail:
    row = db.execute(
        text("""
            INSERT INTO orgs (name, plan_tier, workspace_limit)
            VALUES (:name, :plan_tier, :workspace_limit)
            RETURNING id
        """),
        {"name": payload.name, "plan_tier": payload.plan_tier, "workspace_limit": payload.workspace_limit},
    ).mappings().first()
    db.commit()
    return get_tenant(db, row["id"])


def update_tenant(db: Session, org_id: uuid.UUID, payload: TenantUpdate) -> TenantDetail:
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not updates:
        return get_tenant(db, org_id)
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    db.execute(
        text(f"UPDATE orgs SET {set_clause} WHERE id = :org_id"),
        {**updates, "org_id": org_id},
    )
    db.commit()
    return get_tenant(db, org_id)


def suspend_tenant(db: Session, org_id: uuid.UUID) -> TenantDetail:
    db.execute(
        text("UPDATE orgs SET is_active = false, suspended_at = :now WHERE id = :org_id"),
        {"now": datetime.now(timezone.utc), "org_id": org_id},
    )
    db.commit()
    return get_tenant(db, org_id)
```

- [ ] **Step 5: Replace `tenants/router.py` with full implementation**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.admin.tenants import schemas, service
from src.modules.auth.dependencies import TokenClaims, require_super_admin

router = APIRouter(prefix="/tenants", tags=["admin-tenants"])


@router.get("", response_model=list[schemas.TenantDetail])
def list_tenants(
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.list_tenants(db)


@router.post("", response_model=schemas.TenantDetail, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: schemas.TenantCreate,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.create_tenant(db, payload)


@router.get("/{org_id}", response_model=schemas.TenantDetail)
def get_tenant(
    org_id: uuid.UUID,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return service.get_tenant(db, org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{org_id}", response_model=schemas.TenantDetail)
def update_tenant(
    org_id: uuid.UUID,
    payload: schemas.TenantUpdate,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return service.update_tenant(db, org_id, payload)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{org_id}/suspend", response_model=schemas.TenantDetail)
def suspend_tenant(
    org_id: uuid.UUID,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return service.suspend_tenant(db, org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
pytest tests/admin/test_tenants.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/modules/admin/tenants/ tests/admin/test_tenants.py tests/admin/__init__.py tests/admin/conftest.py
git commit -m "feat(admin): F01 tenant management — CRUD, suspend, usage stats"
```

---

### Task 4: F02 — Prompt Library Management

**Files:**
- Create: `src/modules/admin/prompts/schemas.py`
- Create: `src/modules/admin/prompts/service.py`
- Modify: `src/modules/admin/prompts/router.py`
- Create: `tests/admin/test_prompts.py`

**Interfaces:**
- Consumes: `PromptTemplate` ORM model (existing), `AssessmentSession` with `prompt_template_id` from Task 1
- Produces:
  - `list_prompt_templates(db) -> list[PromptTemplateOut]`
  - `list_versions_for_agent(db, agent_name) -> list[PromptTemplateOut]`
  - `create_prompt_template(db, payload: PromptCreate) -> PromptTemplateOut`
  - `activate_prompt(db, template_id) -> PromptTemplateOut` — atomic swap; raises `LookupError`
  - `rollback_prompt(db, template_id) -> PromptTemplateOut` — activates most-recent previously-active; raises `LookupError`
  - `get_prompt_audit(db, template_id) -> list[PromptAuditEntry]`

- [ ] **Step 1: Write failing tests**

Create `tests/admin/test_prompts.py`:

```python
import pytest

@pytest.mark.asyncio
class TestPromptLibrary:
    async def _create_template(self, async_client, super_admin_token, agent_name="question_generator", version="v1.0"):
        resp = await async_client.post(
            "/admin/prompts",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={
                "agent_name": agent_name,
                "version": version,
                "template_body": f"You are a {agent_name} assistant. Generate a question about {{topic}}.",
            },
        )
        assert resp.status_code == 201
        return resp.json()

    async def test_create_prompt_template(self, async_client, super_admin_token):
        body = await self._create_template(async_client, super_admin_token)
        assert body["agent_name"] == "question_generator"
        assert body["version"] == "v1.0"
        assert body["is_active"] is False

    async def test_list_all_prompts(self, async_client, super_admin_token):
        await self._create_template(async_client, super_admin_token, version="v-list-test")
        resp = await async_client.get(
            "/admin/prompts",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_versions_for_agent(self, async_client, super_admin_token):
        await self._create_template(async_client, super_admin_token, version="v-agent-list")
        resp = await async_client.get(
            "/admin/prompts/question_generator",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert all(t["agent_name"] == "question_generator" for t in resp.json())

    async def test_activate_prompt(self, async_client, super_admin_token):
        t = await self._create_template(async_client, super_admin_token, version="v-activate")
        resp = await async_client.post(
            f"/admin/prompts/{t['id']}/activate",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

    async def test_activate_deactivates_prior(self, async_client, super_admin_token):
        import uuid
        agent = f"scorer-{uuid.uuid4().hex[:6]}"
        t1 = await self._create_template(async_client, super_admin_token, agent_name=agent, version="v1")
        t2 = await self._create_template(async_client, super_admin_token, agent_name=agent, version="v2")

        await async_client.post(
            f"/admin/prompts/{t1['id']}/activate",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        resp = await async_client.post(
            f"/admin/prompts/{t2['id']}/activate",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

        # t1 must now be inactive
        resp2 = await async_client.get(
            f"/admin/prompts/{agent}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        versions = {t["id"]: t for t in resp2.json()}
        assert versions[t1["id"]]["is_active"] is False

    async def test_rollback_prompt(self, async_client, super_admin_token):
        import uuid
        agent = f"report_writer-{uuid.uuid4().hex[:6]}"
        t1 = await self._create_template(async_client, super_admin_token, agent_name=agent, version="v1")
        t2 = await self._create_template(async_client, super_admin_token, agent_name=agent, version="v2")

        await async_client.post(
            f"/admin/prompts/{t1['id']}/activate",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        await async_client.post(
            f"/admin/prompts/{t2['id']}/activate",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )

        resp = await async_client.post(
            f"/admin/prompts/{t2['id']}/rollback",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == t1["id"]
        assert resp.json()["is_active"] is True

    async def test_audit_returns_sessions(self, async_client, super_admin_token):
        t = await self._create_template(async_client, super_admin_token, version="v-audit")
        resp = await async_client.get(
            f"/admin/prompts/{t['id']}/audit",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_requires_super_admin(self, async_client, admin_token):
        resp = await async_client.get(
            "/admin/prompts",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/admin/test_prompts.py -v
```

Expected: all tests FAIL (router still a stub).

- [ ] **Step 3: Create `prompts/schemas.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel


class PromptCreate(BaseModel):
    org_id: uuid.UUID | None = None
    agent_name: str
    version: str
    template_body: str


class PromptTemplateOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID | None
    agent_name: str
    version: str
    template_body: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PromptAuditEntry(BaseModel):
    session_id: uuid.UUID
    org_id: uuid.UUID
    started_at: datetime | None
    completed_at: datetime | None
```

- [ ] **Step 4: Create `prompts/service.py`**

```python
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.modules.admin.prompts.schemas import (
    PromptAuditEntry,
    PromptCreate,
    PromptTemplateOut,
)


def _row_to_out(row) -> PromptTemplateOut:
    return PromptTemplateOut(
        id=row["id"],
        org_id=row["org_id"],
        agent_name=row["agent_name"],
        version=row["version"],
        template_body=row["template_body"],
        is_active=row["is_active"],
        created_at=row["created_at"],
    )


def list_prompt_templates(db: Session) -> list[PromptTemplateOut]:
    rows = db.execute(
        text("SELECT * FROM prompt_templates ORDER BY created_at DESC")
    ).mappings().all()
    return [_row_to_out(r) for r in rows]


def list_versions_for_agent(db: Session, agent_name: str) -> list[PromptTemplateOut]:
    rows = db.execute(
        text("""
            SELECT * FROM prompt_templates
            WHERE agent_name = :agent_name
            ORDER BY created_at DESC
        """),
        {"agent_name": agent_name},
    ).mappings().all()
    return [_row_to_out(r) for r in rows]


def create_prompt_template(db: Session, payload: PromptCreate) -> PromptTemplateOut:
    row = db.execute(
        text("""
            INSERT INTO prompt_templates (org_id, agent_name, version, template_body)
            VALUES (:org_id, :agent_name, :version, :template_body)
            RETURNING *
        """),
        {
            "org_id": payload.org_id,
            "agent_name": payload.agent_name,
            "version": payload.version,
            "template_body": payload.template_body,
        },
    ).mappings().first()
    db.commit()
    return _row_to_out(row)


def activate_prompt(db: Session, template_id: uuid.UUID) -> PromptTemplateOut:
    target = db.execute(
        text("SELECT * FROM prompt_templates WHERE id = :id"),
        {"id": template_id},
    ).mappings().first()
    if not target:
        raise LookupError(f"Template {template_id} not found")

    # Atomic swap: deactivate current active for same (org_id, agent_name), activate target
    db.execute(
        text("""
            UPDATE prompt_templates
            SET is_active = false
            WHERE agent_name = :agent_name
              AND (org_id = :org_id OR (org_id IS NULL AND :org_id IS NULL))
              AND is_active = true
              AND id != :id
        """),
        {"agent_name": target["agent_name"], "org_id": target["org_id"], "id": template_id},
    )
    updated = db.execute(
        text("UPDATE prompt_templates SET is_active = true WHERE id = :id RETURNING *"),
        {"id": template_id},
    ).mappings().first()
    db.commit()
    return _row_to_out(updated)


def rollback_prompt(db: Session, template_id: uuid.UUID) -> PromptTemplateOut:
    target = db.execute(
        text("SELECT * FROM prompt_templates WHERE id = :id"),
        {"id": template_id},
    ).mappings().first()
    if not target:
        raise LookupError(f"Template {template_id} not found")

    # Find the most-recent previously-active version (not the target itself, not currently active)
    prev = db.execute(
        text("""
            SELECT id FROM prompt_templates
            WHERE agent_name = :agent_name
              AND (org_id = :org_id OR (org_id IS NULL AND :org_id IS NULL))
              AND id != :id
              AND is_active = false
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"agent_name": target["agent_name"], "org_id": target["org_id"], "id": template_id},
    ).mappings().first()
    if not prev:
        raise LookupError("No previous version available for rollback")

    return activate_prompt(db, prev["id"])


def get_prompt_audit(db: Session, template_id: uuid.UUID) -> list[PromptAuditEntry]:
    rows = db.execute(
        text("""
            SELECT s.id AS session_id, s.org_id, s.started_at, s.completed_at
            FROM assessment_sessions s
            WHERE s.prompt_template_id = :template_id
            ORDER BY s.started_at DESC
        """),
        {"template_id": template_id},
    ).mappings().all()
    return [
        PromptAuditEntry(
            session_id=r["session_id"],
            org_id=r["org_id"],
            started_at=r["started_at"],
            completed_at=r["completed_at"],
        )
        for r in rows
    ]
```

- [ ] **Step 5: Replace `prompts/router.py` with full implementation**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.admin.prompts import schemas, service
from src.modules.auth.dependencies import TokenClaims, require_super_admin

router = APIRouter(prefix="/prompts", tags=["admin-prompts"])


@router.get("", response_model=list[schemas.PromptTemplateOut])
def list_prompts(
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.list_prompt_templates(db)


@router.get("/{agent_name}", response_model=list[schemas.PromptTemplateOut])
def list_versions(
    agent_name: str,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.list_versions_for_agent(db, agent_name)


@router.post("", response_model=schemas.PromptTemplateOut, status_code=status.HTTP_201_CREATED)
def create_prompt(
    payload: schemas.PromptCreate,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.create_prompt_template(db, payload)


@router.post("/{template_id}/activate", response_model=schemas.PromptTemplateOut)
def activate_prompt(
    template_id: uuid.UUID,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return service.activate_prompt(db, template_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{template_id}/rollback", response_model=schemas.PromptTemplateOut)
def rollback_prompt(
    template_id: uuid.UUID,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        return service.rollback_prompt(db, template_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{template_id}/audit", response_model=list[schemas.PromptAuditEntry])
def get_audit(
    template_id: uuid.UUID,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.get_prompt_audit(db, template_id)
```

**Note:** FastAPI matches routes top-to-bottom. `GET /admin/prompts/{agent_name}` and `GET /admin/prompts/{template_id}/audit` both have a path param. The `/{agent_name}` list route is registered first; the `/{template_id}/audit` route has a second path segment `/audit` so FastAPI correctly distinguishes them.

- [ ] **Step 6: Run tests — expect PASS**

```bash
pytest tests/admin/test_prompts.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/modules/admin/prompts/ tests/admin/test_prompts.py
git commit -m "feat(admin): F02 prompt library — versioned create, activate, rollback, audit"
```

---

### Task 5: F03 — Model Routing Configuration

**Files:**
- Create: `src/modules/admin/routing/schemas.py`
- Create: `src/modules/admin/routing/service.py`
- Modify: `src/modules/admin/routing/router.py`
- Create: `tests/admin/test_routing.py`

**Interfaces:**
- Consumes: `ModelRoutingConfig` ORM model from Task 1; `get_redis()` from `src.database`
- Produces:
  - `get_routing_config(db, redis, agent_name: str) -> RoutingConfigOut` — Redis cache with 30s TTL
  - `list_routing_configs(db) -> list[RoutingConfigOut]`
  - `update_routing_config(db, redis, agent_name, payload: RoutingUpdate, updated_by: uuid.UUID) -> RoutingConfigOut`
  - Redis key pattern: `routing:{agent_name}`

- [ ] **Step 1: Write failing tests**

Create `tests/admin/test_routing.py`:

```python
import pytest


@pytest.mark.asyncio
class TestModelRouting:
    async def test_list_routing_configs(self, async_client, super_admin_token):
        resp = await async_client.get(
            "/admin/routing",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        agent_names = [r["agent_name"] for r in body]
        assert "question_generator" in agent_names
        assert "report_writer" in agent_names
        assert "scorer" in agent_names

    async def test_update_routing_config(self, async_client, super_admin_token):
        resp = await async_client.patch(
            "/admin/routing/question_generator",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"model_id": "claude-haiku-4-5-20251001"},
        )
        assert resp.status_code == 200
        assert resp.json()["model_id"] == "claude-haiku-4-5-20251001"
        assert resp.json()["agent_name"] == "question_generator"

    async def test_update_invalidates_redis_cache(self, async_client, super_admin_token, r):
        # Seed a value in Redis as if it were cached
        r.setex("routing:report_writer", 30, '{"agent_name":"report_writer","provider":"anthropic","model_id":"old-model","fallback_provider":null,"fallback_model_id":null}')
        assert r.get("routing:report_writer") is not None

        await async_client.patch(
            "/admin/routing/report_writer",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"model_id": "claude-sonnet-5"},
        )
        # Cache should be cleared after update
        assert r.get("routing:report_writer") is None

    async def test_update_unknown_agent_returns_404(self, async_client, super_admin_token):
        resp = await async_client.patch(
            "/admin/routing/nonexistent_agent",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"model_id": "some-model"},
        )
        assert resp.status_code == 404

    async def test_requires_super_admin(self, async_client, admin_token):
        resp = await async_client.get(
            "/admin/routing",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/admin/test_routing.py -v
```

Expected: all tests FAIL (router still a stub).

- [ ] **Step 3: Create `routing/schemas.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel


class RoutingConfigOut(BaseModel):
    agent_name: str
    provider: str
    model_id: str
    fallback_provider: str | None
    fallback_model_id: str | None
    updated_by: uuid.UUID | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoutingUpdate(BaseModel):
    provider: str | None = None
    model_id: str | None = None
    fallback_provider: str | None = None
    fallback_model_id: str | None = None
```

- [ ] **Step 4: Create `routing/service.py`**

```python
import json
import uuid

import redis as redis_lib
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.modules.admin.routing.schemas import RoutingConfigOut, RoutingUpdate

_CACHE_TTL = 30  # seconds


def _cache_key(agent_name: str) -> str:
    return f"routing:{agent_name}"


def _row_to_out(row) -> RoutingConfigOut:
    return RoutingConfigOut(
        agent_name=row["agent_name"],
        provider=row["provider"],
        model_id=row["model_id"],
        fallback_provider=row["fallback_provider"],
        fallback_model_id=row["fallback_model_id"],
        updated_by=row["updated_by"],
        updated_at=row["updated_at"],
    )


def list_routing_configs(db: Session) -> list[RoutingConfigOut]:
    rows = db.execute(
        text("SELECT * FROM model_routing_configs WHERE is_active = true ORDER BY agent_name")
    ).mappings().all()
    return [_row_to_out(r) for r in rows]


def get_routing_config(
    db: Session, redis: redis_lib.Redis, agent_name: str
) -> RoutingConfigOut:
    key = _cache_key(agent_name)
    cached = redis.get(key)
    if cached:
        return RoutingConfigOut.model_validate_json(cached)

    row = db.execute(
        text("SELECT * FROM model_routing_configs WHERE agent_name = :agent_name AND is_active = true"),
        {"agent_name": agent_name},
    ).mappings().first()
    if not row:
        raise LookupError(f"No routing config for agent '{agent_name}'")

    result = _row_to_out(row)
    redis.setex(key, _CACHE_TTL, result.model_dump_json())
    return result


def update_routing_config(
    db: Session,
    redis: redis_lib.Redis,
    agent_name: str,
    payload: RoutingUpdate,
    updated_by: uuid.UUID,
) -> RoutingConfigOut:
    existing = db.execute(
        text("SELECT id FROM model_routing_configs WHERE agent_name = :agent_name AND is_active = true"),
        {"agent_name": agent_name},
    ).mappings().first()
    if not existing:
        raise LookupError(f"No routing config for agent '{agent_name}'")

    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    updates["updated_by"] = updated_by
    updates["updated_at"] = "NOW()"

    set_parts = [f"{k} = :{k}" for k in updates if k != "updated_at"]
    set_parts.append("updated_at = NOW()")
    set_clause = ", ".join(set_parts)

    params = {k: v for k, v in updates.items() if k != "updated_at"}
    params["agent_name"] = agent_name

    row = db.execute(
        text(f"""
            UPDATE model_routing_configs
            SET {set_clause}
            WHERE agent_name = :agent_name AND is_active = true
            RETURNING *
        """),
        params,
    ).mappings().first()
    db.commit()

    # Invalidate cache immediately
    redis.delete(_cache_key(agent_name))

    return _row_to_out(row)
```

- [ ] **Step 5: Replace `routing/router.py` with full implementation**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db, get_redis
from src.modules.admin.routing import schemas, service
from src.modules.auth.dependencies import TokenClaims, require_super_admin

router = APIRouter(prefix="/routing", tags=["admin-routing"])


@router.get("", response_model=list[schemas.RoutingConfigOut])
def list_routing_configs(
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.list_routing_configs(db)


@router.patch("/{agent_name}", response_model=schemas.RoutingConfigOut)
def update_routing_config(
    agent_name: str,
    payload: schemas.RoutingUpdate,
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    redis = get_redis()
    try:
        return service.update_routing_config(db, redis, agent_name, payload, claims.sub)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
pytest tests/admin/test_routing.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/modules/admin/routing/ tests/admin/test_routing.py
git commit -m "feat(admin): F03 model routing — hot-swap config, Redis cache, immediate invalidation"
```

---

### Task 6: F04 — System Health & Incident Monitoring

**Files:**
- Create: `src/modules/admin/health/schemas.py`
- Create: `src/modules/admin/health/service.py`
- Modify: `src/modules/admin/health/router.py`
- Create: `tests/admin/test_health.py`

**Interfaces:**
- Consumes: `assessment_sessions`, `integrity_flags`, `hiring_reports` tables; `get_redis()`
- Produces:
  - `get_health_overview(db, redis) -> HealthOverview`
  - `get_incidents(db) -> list[IncidentEntry]`
  - `get_fraud_flag_stats(db) -> FraudFlagStats`

- [ ] **Step 1: Write failing tests**

Create `tests/admin/test_health.py`:

```python
import pytest


@pytest.mark.asyncio
class TestSystemHealth:
    async def test_overview_returns_expected_shape(self, async_client, super_admin_token):
        resp = await async_client.get(
            "/admin/health/overview",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "queue_depth" in body
        assert "error_rate_24h" in body
        assert "p50_seconds" in body
        assert "p95_seconds" in body
        assert "p99_seconds" in body
        assert "total_sessions_24h" in body

    async def test_incidents_returns_list(self, async_client, super_admin_token):
        resp = await async_client.get(
            "/admin/health/incidents",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_fraud_flags_returns_expected_shape(self, async_client, super_admin_token):
        resp = await async_client.get(
            "/admin/health/fraud-flags",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "total_flags" in body
        assert "false_positive_count" in body
        assert "false_positive_rate" in body

    async def test_requires_super_admin(self, async_client, admin_token):
        resp = await async_client.get(
            "/admin/health/overview",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/admin/test_health.py -v
```

Expected: all tests FAIL (router still a stub).

- [ ] **Step 3: Create `health/schemas.py`**

```python
from pydantic import BaseModel


class HealthOverview(BaseModel):
    queue_depth: int
    error_rate_24h: float
    p50_seconds: float | None
    p95_seconds: float | None
    p99_seconds: float | None
    total_sessions_24h: int


class IncidentEntry(BaseModel):
    status: str
    count: int
    last_seen: str | None


class FraudFlagStats(BaseModel):
    total_flags: int
    false_positive_count: int
    false_positive_rate: float
```

- [ ] **Step 4: Create `health/service.py`**

```python
import redis as redis_lib
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.modules.admin.health.schemas import FraudFlagStats, HealthOverview, IncidentEntry


def get_health_overview(db: Session, redis: redis_lib.Redis) -> HealthOverview:
    queue_depth = 0
    try:
        queue_depth = redis.llen("generation_queue") or 0
    except Exception:
        pass

    stats = db.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'error') AS error_count,
            PERCENTILE_CONT(0.50) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at))
            ) FILTER (WHERE status = 'completed' AND completed_at IS NOT NULL AND started_at IS NOT NULL) AS p50,
            PERCENTILE_CONT(0.95) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at))
            ) FILTER (WHERE status = 'completed' AND completed_at IS NOT NULL AND started_at IS NOT NULL) AS p95,
            PERCENTILE_CONT(0.99) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at))
            ) FILTER (WHERE status = 'completed' AND completed_at IS NOT NULL AND started_at IS NOT NULL) AS p99
        FROM assessment_sessions
        WHERE invited_at >= NOW() - INTERVAL '24 hours'
    """)).mappings().first()

    total = int(stats["total"]) if stats["total"] else 0
    error_count = int(stats["error_count"]) if stats["error_count"] else 0

    return HealthOverview(
        queue_depth=int(queue_depth),
        error_rate_24h=error_count / total if total > 0 else 0.0,
        p50_seconds=float(stats["p50"]) if stats["p50"] is not None else None,
        p95_seconds=float(stats["p95"]) if stats["p95"] is not None else None,
        p99_seconds=float(stats["p99"]) if stats["p99"] is not None else None,
        total_sessions_24h=total,
    )


def get_incidents(db: Session) -> list[IncidentEntry]:
    rows = db.execute(text("""
        SELECT
            status,
            COUNT(*) AS count,
            MAX(invited_at)::text AS last_seen
        FROM assessment_sessions
        WHERE status = 'error'
          AND invited_at >= NOW() - INTERVAL '7 days'
        GROUP BY status
        ORDER BY count DESC
    """)).mappings().all()
    return [
        IncidentEntry(
            status=r["status"],
            count=int(r["count"]),
            last_seen=r["last_seen"],
        )
        for r in rows
    ]


def get_fraud_flag_stats(db: Session) -> FraudFlagStats:
    row = db.execute(text("""
        SELECT
            COUNT(DISTINCT f.id) AS total_flags,
            COUNT(DISTINCT f.id) FILTER (
                WHERE hr.verdict IN ('hire', 'strong_hire')
            ) AS false_positives
        FROM integrity_flags f
        JOIN assessment_sessions s ON s.id = f.session_id
        LEFT JOIN hiring_reports hr ON hr.session_id = f.session_id
    """)).mappings().first()

    total = int(row["total_flags"]) if row["total_flags"] else 0
    fp = int(row["false_positives"]) if row["false_positives"] else 0
    return FraudFlagStats(
        total_flags=total,
        false_positive_count=fp,
        false_positive_rate=fp / total if total > 0 else 0.0,
    )
```

- [ ] **Step 5: Replace `health/router.py` with full implementation**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db, get_redis
from src.modules.admin.health import schemas, service
from src.modules.auth.dependencies import TokenClaims, require_super_admin

router = APIRouter(prefix="/health", tags=["admin-health"])


@router.get("/overview", response_model=schemas.HealthOverview)
def health_overview(
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    redis = get_redis()
    return service.get_health_overview(db, redis)


@router.get("/incidents", response_model=list[schemas.IncidentEntry])
def incidents(
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.get_incidents(db)


@router.get("/fraud-flags", response_model=schemas.FraudFlagStats)
def fraud_flags(
    claims: TokenClaims = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return service.get_fraud_flag_stats(db)
```

- [ ] **Step 6: Run all admin tests**

```bash
pytest tests/admin/ -v
```

Expected: all tests PASS.

- [ ] **Step 7: Run full test suite**

```bash
pytest --tb=short -q
```

Expected: 230+ PASS, 0 FAIL.

- [ ] **Step 8: Commit**

```bash
git add src/modules/admin/health/ tests/admin/test_health.py
git commit -m "feat(admin): F04 system health — queue depth, latency percentiles, fraud-flag stats"
```

---

### Task 7: `packages/prompt-library` TypeScript Types

**Files:**
- Modify: `packages/prompt-library/src/index.ts`

**Interfaces:**
- Produces: `AGENT_NAMES`, `PromptVersion`, `ModelRoutingConfig` — consumed by Task 8 frontend

- [ ] **Step 1: Replace `packages/prompt-library/src/index.ts`**

```typescript
export const PROMPT_LIBRARY_VERSION = "0.2.0";

export const AGENT_NAMES = [
  "question_generator",
  "report_writer",
  "scorer",
] as const;

export type AgentName = (typeof AGENT_NAMES)[number];

export interface PromptVersion {
  id: string;
  org_id: string | null;
  agent_name: AgentName | string;
  version: string;
  template_body: string;
  is_active: boolean;
  created_at: string;
}

export interface ModelRoutingConfig {
  agent_name: AgentName | string;
  provider: string;
  model_id: string;
  fallback_provider: string | null;
  fallback_model_id: string | null;
  updated_by: string | null;
  updated_at: string;
}

export interface TenantDetail {
  id: string;
  name: string;
  plan_tier: string;
  workspace_limit: number;
  is_active: boolean;
  suspended_at: string | null;
  created_at: string;
  user_count: number;
  session_count: number;
}

export interface HealthOverview {
  queue_depth: number;
  error_rate_24h: number;
  p50_seconds: number | null;
  p95_seconds: number | null;
  p99_seconds: number | null;
  total_sessions_24h: number;
}

export interface IncidentEntry {
  status: string;
  count: number;
  last_seen: string | null;
}

export interface FraudFlagStats {
  total_flags: number;
  false_positive_count: number;
  false_positive_rate: number;
}
```

- [ ] **Step 2: Build the package**

```bash
cd packages/prompt-library
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add packages/prompt-library/src/index.ts
git commit -m "feat(admin): prompt-library package — AGENT_NAMES, PromptVersion, routing + admin types"
```

---

### Task 8: Frontend — Admin Page Group (4 Tabs)

**Files:**
- Create: `apps/console-web/src/app/(console)/admin/_lib/types.ts`
- Create: `apps/console-web/src/app/(console)/admin/_lib/api.ts`
- Create: `apps/console-web/src/app/(console)/admin/_components/TenantsTab.tsx`
- Create: `apps/console-web/src/app/(console)/admin/_components/PromptsTab.tsx`
- Create: `apps/console-web/src/app/(console)/admin/_components/RoutingTab.tsx`
- Create: `apps/console-web/src/app/(console)/admin/_components/HealthTab.tsx`
- Create: `apps/console-web/src/app/(console)/admin/page.tsx`

**Interfaces:**
- Consumes: `apiFetch` from `@/lib/api/index`; types from `packages/prompt-library` (or local re-export)
- Produces: `/admin` page accessible in the console layout

- [ ] **Step 1: Check `@/lib/api/index` to confirm `apiFetch` signature**

Read `apps/console-web/src/lib/api/index.ts` (or wherever `apiFetch` is defined) to confirm the import path. The analytics module imports it as `import { apiFetch } from "@/lib/api/index"`.

- [ ] **Step 2: Create `_lib/types.ts`**

```typescript
export interface TenantDetail {
  id: string;
  name: string;
  plan_tier: string;
  workspace_limit: number;
  is_active: boolean;
  suspended_at: string | null;
  created_at: string;
  user_count: number;
  session_count: number;
}

export interface PromptVersion {
  id: string;
  org_id: string | null;
  agent_name: string;
  version: string;
  template_body: string;
  is_active: boolean;
  created_at: string;
}

export interface ModelRoutingConfig {
  agent_name: string;
  provider: string;
  model_id: string;
  fallback_provider: string | null;
  fallback_model_id: string | null;
  updated_by: string | null;
  updated_at: string;
}

export interface HealthOverview {
  queue_depth: number;
  error_rate_24h: number;
  p50_seconds: number | null;
  p95_seconds: number | null;
  p99_seconds: number | null;
  total_sessions_24h: number;
}

export interface IncidentEntry {
  status: string;
  count: number;
  last_seen: string | null;
}

export interface FraudFlagStats {
  total_flags: number;
  false_positive_count: number;
  false_positive_rate: number;
}
```

- [ ] **Step 3: Create `_lib/api.ts`**

```typescript
import { apiFetch } from "@/lib/api/index";
import type {
  FraudFlagStats,
  HealthOverview,
  IncidentEntry,
  ModelRoutingConfig,
  PromptVersion,
  TenantDetail,
} from "./types";

export async function fetchTenants(signal?: AbortSignal): Promise<TenantDetail[]> {
  return apiFetch<TenantDetail[]>("/admin/tenants", { signal });
}

export async function createTenant(
  payload: { name: string; plan_tier: string; workspace_limit: number },
  signal?: AbortSignal
): Promise<TenantDetail> {
  return apiFetch<TenantDetail>("/admin/tenants", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
}

export async function suspendTenant(orgId: string, signal?: AbortSignal): Promise<TenantDetail> {
  return apiFetch<TenantDetail>(`/admin/tenants/${orgId}/suspend`, {
    method: "DELETE",
    signal,
  });
}

export async function fetchPrompts(signal?: AbortSignal): Promise<PromptVersion[]> {
  return apiFetch<PromptVersion[]>("/admin/prompts", { signal });
}

export async function activatePrompt(id: string, signal?: AbortSignal): Promise<PromptVersion> {
  return apiFetch<PromptVersion>(`/admin/prompts/${id}/activate`, { method: "POST", signal });
}

export async function rollbackPrompt(id: string, signal?: AbortSignal): Promise<PromptVersion> {
  return apiFetch<PromptVersion>(`/admin/prompts/${id}/rollback`, { method: "POST", signal });
}

export async function fetchRoutingConfigs(signal?: AbortSignal): Promise<ModelRoutingConfig[]> {
  return apiFetch<ModelRoutingConfig[]>("/admin/routing", { signal });
}

export async function updateRoutingConfig(
  agentName: string,
  payload: Partial<Pick<ModelRoutingConfig, "provider" | "model_id" | "fallback_provider" | "fallback_model_id">>,
  signal?: AbortSignal
): Promise<ModelRoutingConfig> {
  return apiFetch<ModelRoutingConfig>(`/admin/routing/${agentName}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
}

export async function fetchHealthOverview(signal?: AbortSignal): Promise<HealthOverview> {
  return apiFetch<HealthOverview>("/admin/health/overview", { signal });
}

export async function fetchIncidents(signal?: AbortSignal): Promise<IncidentEntry[]> {
  return apiFetch<IncidentEntry[]>("/admin/health/incidents", { signal });
}

export async function fetchFraudFlags(signal?: AbortSignal): Promise<FraudFlagStats> {
  return apiFetch<FraudFlagStats>("/admin/health/fraud-flags", { signal });
}
```

- [ ] **Step 4: Create `_components/TenantsTab.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { fetchTenants, suspendTenant } from "../_lib/api";
import type { TenantDetail } from "../_lib/types";

export default function TenantsTab() {
  const [tenants, setTenants] = useState<TenantDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchTenants(controller.signal)
      .then((data) => { if (!controller.signal.aborted) setTenants(data); })
      .catch((err) => { if (err?.name !== "AbortError") setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  async function handleSuspend(orgId: string) {
    const updated = await suspendTenant(orgId);
    setTenants((prev) => prev.map((t) => (t.id === orgId ? updated : t)));
  }

  if (loading) {
    return <div className="animate-pulse h-40 bg-slate-100 rounded-lg" />;
  }
  if (error) {
    return <div className="text-red-600 text-sm p-4 border border-red-200 rounded-lg">Failed to load tenants: {error}</div>;
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            <th className="px-4 py-3 text-left font-medium">Name</th>
            <th className="px-4 py-3 text-left font-medium">Plan</th>
            <th className="px-4 py-3 text-right font-medium">Users</th>
            <th className="px-4 py-3 text-right font-medium">Sessions</th>
            <th className="px-4 py-3 text-left font-medium">Status</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tenants.map((t) => (
            <tr key={t.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 font-medium text-slate-800">{t.name}</td>
              <td className="px-4 py-3 text-slate-600">{t.plan_tier}</td>
              <td className="px-4 py-3 text-right text-slate-600">{t.user_count}</td>
              <td className="px-4 py-3 text-right text-slate-600">{t.session_count}</td>
              <td className="px-4 py-3">
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${t.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                  {t.is_active ? "Active" : "Suspended"}
                </span>
              </td>
              <td className="px-4 py-3 text-right">
                {t.is_active && (
                  <button
                    onClick={() => handleSuspend(t.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Suspend
                  </button>
                )}
              </td>
            </tr>
          ))}
          {tenants.length === 0 && (
            <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400 text-sm">No tenants found</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 5: Create `_components/PromptsTab.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { fetchPrompts, activatePrompt, rollbackPrompt } from "../_lib/api";
import type { PromptVersion } from "../_lib/types";

export default function PromptsTab() {
  const [templates, setTemplates] = useState<PromptVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchPrompts(controller.signal)
      .then((data) => { if (!controller.signal.aborted) setTemplates(data); })
      .catch((err) => { if (err?.name !== "AbortError") setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  async function handleActivate(id: string) {
    const updated = await activatePrompt(id);
    setTemplates((prev) =>
      prev.map((t) =>
        t.agent_name === updated.agent_name && t.org_id === updated.org_id
          ? { ...t, is_active: t.id === updated.id }
          : t
      )
    );
  }

  async function handleRollback(id: string) {
    const updated = await rollbackPrompt(id);
    setTemplates((prev) =>
      prev.map((t) =>
        t.agent_name === updated.agent_name && t.org_id === updated.org_id
          ? { ...t, is_active: t.id === updated.id }
          : t
      )
    );
  }

  if (loading) return <div className="animate-pulse h-40 bg-slate-100 rounded-lg" />;
  if (error) return <div className="text-red-600 text-sm p-4 border border-red-200 rounded-lg">Failed to load prompts: {error}</div>;

  const grouped = templates.reduce<Record<string, PromptVersion[]>>((acc, t) => {
    (acc[t.agent_name] ??= []).push(t);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([agentName, versions]) => (
        <div key={agentName} className="rounded-lg border border-slate-200 bg-white overflow-hidden">
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-200">
            <h3 className="text-sm font-semibold text-slate-700">{agentName}</h3>
          </div>
          <table className="w-full text-sm">
            <thead className="text-slate-500">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Version</th>
                <th className="px-4 py-2 text-left font-medium">Created</th>
                <th className="px-4 py-2 text-left font-medium">Status</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {versions.map((v) => (
                <tr key={v.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2 font-mono text-slate-700">{v.version}</td>
                  <td className="px-4 py-2 text-slate-500">{new Date(v.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-2">
                    {v.is_active && (
                      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700">Active</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right space-x-3">
                    {!v.is_active && (
                      <button onClick={() => handleActivate(v.id)} className="text-xs text-blue-600 hover:underline">Activate</button>
                    )}
                    {v.is_active && (
                      <button onClick={() => handleRollback(v.id)} className="text-xs text-amber-600 hover:underline">Rollback</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
      {templates.length === 0 && (
        <div className="text-slate-400 text-sm text-center py-12">No prompt templates yet</div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Create `_components/RoutingTab.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { fetchRoutingConfigs, updateRoutingConfig } from "../_lib/api";
import type { ModelRoutingConfig } from "../_lib/types";

export default function RoutingTab() {
  const [configs, setConfigs] = useState<ModelRoutingConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Record<string, Partial<ModelRoutingConfig>>>({});

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchRoutingConfigs(controller.signal)
      .then((data) => { if (!controller.signal.aborted) setConfigs(data); })
      .catch((err) => { if (err?.name !== "AbortError") setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  async function handleSave(agentName: string) {
    const patch = editing[agentName];
    if (!patch) return;
    const updated = await updateRoutingConfig(agentName, patch);
    setConfigs((prev) => prev.map((c) => (c.agent_name === agentName ? updated : c)));
    setEditing((prev) => { const next = { ...prev }; delete next[agentName]; return next; });
  }

  if (loading) return <div className="animate-pulse h-40 bg-slate-100 rounded-lg" />;
  if (error) return <div className="text-red-600 text-sm p-4 border border-red-200 rounded-lg">Failed to load routing config: {error}</div>;

  return (
    <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            <th className="px-4 py-3 text-left font-medium">Agent</th>
            <th className="px-4 py-3 text-left font-medium">Provider</th>
            <th className="px-4 py-3 text-left font-medium">Model</th>
            <th className="px-4 py-3 text-left font-medium">Fallback Model</th>
            <th className="px-4 py-3 text-right font-medium">Last Updated</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {configs.map((c) => {
            const edit = editing[c.agent_name] ?? {};
            return (
              <tr key={c.agent_name} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-slate-700">{c.agent_name}</td>
                <td className="px-4 py-3">
                  <input
                    className="border border-slate-300 rounded px-2 py-1 text-sm w-28"
                    value={edit.provider ?? c.provider}
                    onChange={(e) => setEditing((prev) => ({ ...prev, [c.agent_name]: { ...prev[c.agent_name], provider: e.target.value } }))}
                  />
                </td>
                <td className="px-4 py-3">
                  <input
                    className="border border-slate-300 rounded px-2 py-1 text-sm w-48"
                    value={edit.model_id ?? c.model_id}
                    onChange={(e) => setEditing((prev) => ({ ...prev, [c.agent_name]: { ...prev[c.agent_name], model_id: e.target.value } }))}
                  />
                </td>
                <td className="px-4 py-3">
                  <input
                    className="border border-slate-300 rounded px-2 py-1 text-sm w-48"
                    placeholder="none"
                    value={edit.fallback_model_id ?? c.fallback_model_id ?? ""}
                    onChange={(e) => setEditing((prev) => ({ ...prev, [c.agent_name]: { ...prev[c.agent_name], fallback_model_id: e.target.value || null } }))}
                  />
                </td>
                <td className="px-4 py-3 text-right text-slate-500">{new Date(c.updated_at).toLocaleDateString()}</td>
                <td className="px-4 py-3 text-right">
                  {editing[c.agent_name] && (
                    <button onClick={() => handleSave(c.agent_name)} className="text-xs text-blue-600 hover:underline">Save</button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="px-4 py-2 text-xs text-slate-400 border-t border-slate-100">Changes take effect within 30s — no redeploy needed.</p>
    </div>
  );
}
```

- [ ] **Step 7: Create `_components/HealthTab.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { fetchHealthOverview, fetchIncidents, fetchFraudFlags } from "../_lib/api";
import type { FraudFlagStats, HealthOverview, IncidentEntry } from "../_lib/types";

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 text-center">
      <div className="text-2xl font-bold text-slate-900">{value}</div>
      <div className="text-sm text-slate-500 mt-1">{label}</div>
    </div>
  );
}

function fmt(v: number | null): string {
  return v == null ? "—" : `${v.toFixed(1)}s`;
}

export default function HealthTab() {
  const [overview, setOverview] = useState<HealthOverview | null>(null);
  const [incidents, setIncidents] = useState<IncidentEntry[]>([]);
  const [fraud, setFraud] = useState<FraudFlagStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    Promise.all([
      fetchHealthOverview(controller.signal),
      fetchIncidents(controller.signal),
      fetchFraudFlags(controller.signal),
    ])
      .then(([ov, inc, fr]) => {
        if (!controller.signal.aborted) {
          setOverview(ov);
          setIncidents(inc);
          setFraud(fr);
        }
      })
      .catch((err) => { if (err?.name !== "AbortError") setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  if (loading) return <div className="animate-pulse h-40 bg-slate-100 rounded-lg" />;
  if (error) return <div className="text-red-600 text-sm p-4 border border-red-200 rounded-lg">Failed to load health data: {error}</div>;

  return (
    <div className="space-y-6">
      {overview && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <StatTile label="Queue Depth" value={overview.queue_depth} />
          <StatTile label="Error Rate (24h)" value={`${(overview.error_rate_24h * 100).toFixed(1)}%`} />
          <StatTile label="Sessions (24h)" value={overview.total_sessions_24h} />
          <StatTile label="p50 Latency" value={fmt(overview.p50_seconds)} />
          <StatTile label="p95 Latency" value={fmt(overview.p95_seconds)} />
          <StatTile label="p99 Latency" value={fmt(overview.p99_seconds)} />
        </div>
      )}

      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <h3 className="text-sm font-semibold text-slate-700 mb-4">Incidents (Last 7 Days)</h3>
        {incidents.length === 0 ? (
          <p className="text-slate-400 text-sm text-center py-4">No incidents</p>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="text-slate-500 text-left"><th className="pb-2">Status</th><th className="pb-2">Count</th><th className="pb-2">Last Seen</th></tr></thead>
            <tbody>{incidents.map((i) => (
              <tr key={i.status} className="border-t border-slate-100">
                <td className="py-2 font-mono text-red-600">{i.status}</td>
                <td className="py-2">{i.count}</td>
                <td className="py-2 text-slate-500">{i.last_seen ?? "—"}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </div>

      {fraud && (
        <div className="rounded-lg border border-slate-200 bg-white p-6">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Fraud Flag Summary</h3>
          <div className="grid grid-cols-3 gap-4">
            <StatTile label="Total Flags" value={fraud.total_flags} />
            <StatTile label="False Positives" value={fraud.false_positive_count} />
            <StatTile label="False Positive Rate" value={`${(fraud.false_positive_rate * 100).toFixed(1)}%`} />
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 8: Create `admin/page.tsx`**

```tsx
"use client";

import { useState } from "react";
import TenantsTab from "./_components/TenantsTab";
import PromptsTab from "./_components/PromptsTab";
import RoutingTab from "./_components/RoutingTab";
import HealthTab from "./_components/HealthTab";

type Tab = "tenants" | "prompts" | "routing" | "health";

const TABS: { id: Tab; label: string }[] = [
  { id: "tenants", label: "Tenants" },
  { id: "prompts", label: "Prompt Library" },
  { id: "routing", label: "Model Routing" },
  { id: "health", label: "System Health" },
];

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<Tab>("tenants");
  const [mounted, setMounted] = useState<Set<Tab>>(new Set<Tab>(["tenants"]));

  function handleTabChange(tab: Tab) {
    setActiveTab(tab);
    setMounted((prev) => {
      const next = new Set(prev);
      next.add(tab);
      return next;
    });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-800">Platform Administration</h1>

      <div className="border-b border-slate-200">
        <nav className="-mb-px flex gap-6">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-slate-800 text-slate-900"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      <div className={activeTab === "tenants" ? "" : "hidden"}>
        {mounted.has("tenants") && <TenantsTab />}
      </div>
      <div className={activeTab === "prompts" ? "" : "hidden"}>
        {mounted.has("prompts") && <PromptsTab />}
      </div>
      <div className={activeTab === "routing" ? "" : "hidden"}>
        {mounted.has("routing") && <RoutingTab />}
      </div>
      <div className={activeTab === "health" ? "" : "hidden"}>
        {mounted.has("health") && <HealthTab />}
      </div>
    </div>
  );
}
```

- [ ] **Step 9: TypeScript check**

```bash
cd apps/console-web
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 10: Commit**

```bash
git add apps/console-web/src/app/\(console\)/admin/
git commit -m "feat(admin): frontend admin page — Tenants, Prompt Library, Model Routing, System Health tabs"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Task covering it |
|---|---|
| super_admin role + require_super_admin | Task 2 |
| Migration 0007 (role, orgs, model_routing_configs, prompt_template_id) | Task 1 |
| F01 Tenant CRUD + suspend | Task 3 |
| F02 Prompt versioning, activate, rollback | Task 4 |
| F02 Prompt traceability (/audit) | Task 4 |
| F03 Model routing hot-swap + Redis cache | Task 5 |
| F04 Health overview, incidents, fraud flags | Task 6 |
| packages/prompt-library TS types | Task 7 |
| Frontend 4-tab admin page | Task 8 |
| main.py wiring | Task 2 |

All spec sections covered. ✅

**Placeholder scan:** No TBD, no TODO, no "similar to Task N" references. All code blocks are complete.

**Type consistency:** `RoutingConfigOut` defined in Task 5 `schemas.py`; used in Task 5 router and service only. `TenantDetail` defined in Task 3 schemas; `PromptTemplateOut` in Task 4; `HealthOverview`/`IncidentEntry`/`FraudFlagStats` in Task 6. Frontend `_lib/types.ts` mirrors these shapes. No cross-task type name collisions.

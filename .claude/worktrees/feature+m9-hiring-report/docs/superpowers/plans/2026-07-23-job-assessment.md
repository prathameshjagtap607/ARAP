# Job Assessment Builder & Job Description Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement M1 (Job Assessment Builder: CRUD, competency library, templates/clone, candidate invitation) and the Job Description Agent (§7) that produces a stored `job_profile` JSON.

**Architecture:** Standard FastAPI module pattern (schemas → service → router) matching the existing auth module. JD agent lives at `agents/job_description/` and is called synchronously from the job_assessments service after every create/update. Three new columns are added to `job_assessments` via Alembic migration 0002.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, Pydantic v2, anthropic SDK (claude-haiku-4-5-20251001), pytest + httpx AsyncClient, unittest.mock.

## Global Constraints

- SQLAlchemy 2.x style: `Mapped[T]` + `mapped_column()` everywhere — no legacy `Column()`.
- Pydantic v2: use `model_config = ConfigDict(from_attributes=True)` on response schemas.
- All endpoints: `Depends(require_user)` — role "user" OR "admin" may create/manage assessments.
- `org_id` always sourced from `claims.org_id` (never from request body).
- Weightage validation: `abs(sum(weights.values()) - 100) > 0.01` → raise `ValueError`.
- JD agent failures are non-fatal: log + leave `job_profile=None`; assessment is still created.
- Test pattern: async httpx client + real PostgreSQL test DB (`postgresql://arap:arap@localhost:5434/arap_test`).
- Anthropic model: `claude-haiku-4-5-20251001` (normalization task per tier rules).
- All `git commit` messages use format: `[TASK-001] <type>: <what>`.
- Working directory for all commands: `services/orchestrator-api/` unless noted.

---

### Task 1: Migration 0002 + JobAssessment model columns

**Files:**
- Create: `services/orchestrator-api/migrations/versions/0002_job_assessment_templates_profile.py`
- Modify: `services/orchestrator-api/src/models/job_assessments.py`

**Interfaces:**
- Produces: `JobAssessment.is_template: bool`, `JobAssessment.role_family: str | None`, `JobAssessment.job_profile: dict | None` — used by every later task.

- [ ] **Step 1: Write the migration file**

Create `services/orchestrator-api/migrations/versions/0002_job_assessment_templates_profile.py`:

```python
"""add is_template role_family job_profile to job_assessments

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_assessments",
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "job_assessments",
        sa.Column("role_family", sa.Text(), nullable=True),
    )
    op.add_column(
        "job_assessments",
        sa.Column("job_profile", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("job_assessments", "job_profile")
    op.drop_column("job_assessments", "role_family")
    op.drop_column("job_assessments", "is_template")
```

- [ ] **Step 2: Update the SQLAlchemy model**

Replace the full contents of `services/orchestrator-api/src/models/job_assessments.py`:

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text,
    func, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class JobAssessment(Base):
    __tablename__ = "job_assessments"
    __table_args__ = (
        CheckConstraint(
            "difficulty_level IN ('junior','mid','senior','executive')",
            name="ck_job_assessments_difficulty_level",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String)
    experience_min: Mapped[Optional[int]] = mapped_column(Integer)
    experience_max: Mapped[Optional[int]] = mapped_column(Integer)
    required_skills: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    preferred_skills: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    responsibilities: Mapped[Optional[str]] = mapped_column(Text)
    education: Mapped[Optional[str]] = mapped_column(Text)
    certifications: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    behavioral_competencies: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    leadership_competencies: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    culture_values: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    difficulty_level: Mapped[str] = mapped_column(String, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    competency_weightage: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_template: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    role_family: Mapped[Optional[str]] = mapped_column(Text)
    job_profile: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 3: Run the migration against the dev DB**

```bash
cd services/orchestrator-api
alembic upgrade head
```

Expected output ends with: `Running upgrade 0001 -> 0002, add is_template role_family job_profile to job_assessments`

- [ ] **Step 4: Commit**

```bash
git add migrations/versions/0002_job_assessment_templates_profile.py src/models/job_assessments.py
git commit -m "[TASK-001] feat: add is_template, role_family, job_profile columns to job_assessments"
```

---

### Task 2: ANTHROPIC_API_KEY config + Job Description Agent

**Files:**
- Modify: `services/orchestrator-api/pyproject.toml` (add anthropic dep + PYTHONPATH + test env)
- Modify: `services/orchestrator-api/src/config.py`
- Create: `agents/job_description/prompts.py`
- Create: `agents/job_description/agent.py`
- Create: `services/orchestrator-api/tests/job_description/__init__.py`
- Create: `services/orchestrator-api/tests/job_description/test_agent.py`

**Interfaces:**
- Produces: `run_job_description_agent(db: Session, assessment: JobAssessment) -> None` — called by job_assessments service in Tasks 4–6.

- [ ] **Step 1: Add anthropic SDK + PYTHONPATH to pyproject.toml**

Replace `services/orchestrator-api/pyproject.toml` with:

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
    "pydantic[email]>=2.0",
    "PyJWT>=2.8",
    "passlib[bcrypt]>=1.7.4",
    "bcrypt>=4.0.1,<5.0",
    "redis>=5.0",
    "anthropic>=0.28",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-env>=1.1",
    "httpx>=0.27",
    "anyio[asyncio]>=4.0",
    "pytest-asyncio>=0.23",
    "fakeredis>=2.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
pythonpath = [".", "../.."]
env = [
    "TEST_DATABASE_URL=postgresql://arap:arap@localhost:5434/arap_test",
    "DATABASE_URL=postgresql://arap:arap@localhost:5433/arap_dev",
    "SECRET_KEY=test-secret-key-not-for-production",
    "JWT_SECRET_KEY=test-jwt-secret-key-not-for-production",
    "ANTHROPIC_API_KEY=test-anthropic-key-not-real",
]
```

- [ ] **Step 2: Install the new dependency**

```bash
cd services/orchestrator-api
pip install -e ".[dev]"
```

Expected: `Successfully installed anthropic-...`

- [ ] **Step 3: Add ANTHROPIC_API_KEY to config.py**

Replace the full contents of `services/orchestrator-api/src/config.py`:

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

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    LOGIN_TOKEN_EXPIRE_MINUTES: int = 15
    REDIS_URL: str = "redis://localhost:6379/0"

    ANTHROPIC_API_KEY: str


settings = Settings()
```

- [ ] **Step 4: Write the failing agent test**

Create `services/orchestrator-api/tests/job_description/__init__.py` (empty).

Create `services/orchestrator-api/tests/job_description/test_agent.py`:

```python
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.models.base import Base
import src.models  # noqa: F401
from src.models.orgs import Org
from src.models.users import User
from src.models.job_assessments import JobAssessment

TEST_DB_URL = "postgresql://arap:arap@localhost:5434/arap_test"


@pytest.fixture(scope="module")
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
def db(engine):
    Session = sessionmaker(engine)
    s = Session()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def assessment(db):
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    org = Org(name="AgentTestOrg")
    db.add(org)
    db.flush()
    user = User(
        org_id=org.id, email="u@t.com", role="user",
        password_hash=pwd.hash("x"),
    )
    db.add(user)
    db.flush()
    job = JobAssessment(
        org_id=org.id,
        title="Senior Python Engineer",
        department="Engineering",
        difficulty_level="senior",
        duration_minutes=60,
        required_skills=["Python", "FastAPI"],
        preferred_skills=["Docker"],
        behavioral_competencies=["problem_solving"],
        leadership_competencies=["mentoring"],
        competency_weightage={"problem_solving": 60.0, "mentoring": 40.0},
        created_by=user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


_FAKE_PROFILE = {
    "normalized_title": "Senior Python Engineer",
    "role_summary": "Builds backend services.",
    "key_responsibilities": ["Design APIs"],
    "required_skills": ["Python", "FastAPI"],
    "preferred_skills": ["Docker"],
    "education_requirements": "Bachelor's or equivalent",
    "certifications": [],
    "competency_weightage_map": {"problem_solving": 60.0, "mentoring": 40.0},
    "difficulty_level": "senior",
    "generated_at": "2026-07-23T00:00:00",
}


def _make_mock_client():
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.input = _FAKE_PROFILE

    message = MagicMock()
    message.content = [tool_use_block]

    client = MagicMock()
    client.messages.create.return_value = message
    return client


def test_agent_writes_job_profile(db, assessment):
    from agents.job_description.agent import run_job_description_agent

    with patch("agents.job_description.agent.anthropic.Anthropic", return_value=_make_mock_client()):
        run_job_description_agent(db, assessment)

    db.refresh(assessment)
    assert assessment.job_profile is not None
    assert assessment.job_profile["normalized_title"] == "Senior Python Engineer"
    assert "competency_weightage_map" in assessment.job_profile
    assert assessment.job_profile["difficulty_level"] == "senior"


def test_agent_non_fatal_on_api_error(db, assessment):
    from agents.job_description.agent import run_job_description_agent

    assessment.job_profile = None
    db.commit()

    failing_client = MagicMock()
    failing_client.messages.create.side_effect = Exception("API down")

    with patch("agents.job_description.agent.anthropic.Anthropic", return_value=failing_client):
        run_job_description_agent(db, assessment)

    db.refresh(assessment)
    assert assessment.job_profile is None
```

- [ ] **Step 5: Run the test to confirm it fails (ImportError expected)**

```bash
cd services/orchestrator-api
pytest tests/job_description/test_agent.py -v
```

Expected: `ModuleNotFoundError: No module named 'agents.job_description.agent'`

- [ ] **Step 6: Create prompts.py**

Create `agents/job_description/prompts.py`:

```python
SYSTEM_PROMPT = (
    "You are a job description normalization assistant. "
    "Given raw job assessment data, produce a structured job_profile JSON "
    "using the provided tool. Be concise and factual — do not invent requirements "
    "not present in the input."
)

JOB_PROFILE_TOOL = {
    "name": "produce_job_profile",
    "description": "Produce a normalized job_profile from the raw assessment data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "normalized_title": {"type": "string"},
            "role_summary": {"type": "string"},
            "key_responsibilities": {"type": "array", "items": {"type": "string"}},
            "required_skills": {"type": "array", "items": {"type": "string"}},
            "preferred_skills": {"type": "array", "items": {"type": "string"}},
            "education_requirements": {"type": "string"},
            "certifications": {"type": "array", "items": {"type": "string"}},
            "competency_weightage_map": {
                "type": "object",
                "additionalProperties": {"type": "number"},
            },
            "difficulty_level": {
                "type": "string",
                "enum": ["junior", "mid", "senior", "executive"],
            },
            "generated_at": {"type": "string", "format": "date-time"},
        },
        "required": [
            "normalized_title", "role_summary", "key_responsibilities",
            "required_skills", "preferred_skills", "education_requirements",
            "certifications", "competency_weightage_map", "difficulty_level",
            "generated_at",
        ],
    },
}
```

- [ ] **Step 7: Create agent.py**

Create `agents/job_description/agent.py`:

```python
import logging
from datetime import UTC, datetime

import anthropic
from sqlalchemy.orm import Session

from agents.job_description.prompts import JOB_PROFILE_TOOL, SYSTEM_PROMPT
from src.config import settings

logger = logging.getLogger(__name__)


def _build_user_message(assessment) -> str:
    return (
        f"Title: {assessment.title}\n"
        f"Department: {assessment.department or 'N/A'}\n"
        f"Difficulty: {assessment.difficulty_level}\n"
        f"Experience: {assessment.experience_min or 0}–{assessment.experience_max or 0} years\n"
        f"Required skills: {', '.join(assessment.required_skills or [])}\n"
        f"Preferred skills: {', '.join(assessment.preferred_skills or [])}\n"
        f"Responsibilities: {assessment.responsibilities or 'N/A'}\n"
        f"Education: {assessment.education or 'N/A'}\n"
        f"Certifications: {', '.join(assessment.certifications or [])}\n"
        f"Behavioral competencies: {', '.join(assessment.behavioral_competencies or [])}\n"
        f"Leadership competencies: {', '.join(assessment.leadership_competencies or [])}\n"
        f"Culture values: {', '.join(assessment.culture_values or [])}\n"
        f"Competency weightage: {assessment.competency_weightage}\n"
    )


def run_job_description_agent(db: Session, assessment) -> None:
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[JOB_PROFILE_TOOL],
            tool_choice={"type": "tool", "name": "produce_job_profile"},
            messages=[{"role": "user", "content": _build_user_message(assessment)}],
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        profile = dict(tool_block.input)
        profile["generated_at"] = datetime.now(UTC).isoformat()
        assessment.job_profile = profile
        db.commit()
    except Exception:
        logger.exception("JD agent failed for assessment %s — job_profile left NULL", assessment.id)
```

- [ ] **Step 8: Run tests — both must pass**

```bash
cd services/orchestrator-api
pytest tests/job_description/test_agent.py -v
```

Expected:
```
PASSED tests/job_description/test_agent.py::test_agent_writes_job_profile
PASSED tests/job_description/test_agent.py::test_agent_non_fatal_on_api_error
```

- [ ] **Step 9: Commit**

```bash
cd D:/staging/ARAP1
git add agents/job_description/prompts.py agents/job_description/agent.py
git add services/orchestrator-api/pyproject.toml services/orchestrator-api/src/config.py
git add services/orchestrator-api/tests/job_description/
git commit -m "[TASK-001] feat: implement job_description agent with Haiku structured output"
```

---

### Task 3: Competency Library module

**Files:**
- Create: `services/orchestrator-api/src/modules/competency_library/__init__.py`
- Create: `services/orchestrator-api/src/modules/competency_library/schemas.py`
- Create: `services/orchestrator-api/src/modules/competency_library/service.py`
- Create: `services/orchestrator-api/src/modules/competency_library/router.py`
- Create: `services/orchestrator-api/tests/competency_library/__init__.py`
- Create: `services/orchestrator-api/tests/competency_library/conftest.py`
- Create: `services/orchestrator-api/tests/competency_library/test_crud.py`

**Interfaces:**
- Consumes: `require_user` from `src.modules.auth.dependencies`, `get_db` from `src.database`, `TokenClaims.org_id`.
- Produces: router mountable at `app.include_router(competency_library_router)`.

- [ ] **Step 1: Write the failing tests**

Create `services/orchestrator-api/tests/competency_library/__init__.py` (empty).

Create `services/orchestrator-api/tests/competency_library/conftest.py`:

```python
import os
import pytest
import pytest_asyncio
import fakeredis
from httpx import ASGITransport, AsyncClient
from passlib.context import CryptContext
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.models.base import Base
import src.models  # noqa: F401
from src.models.orgs import Org
from src.models.users import User
from src.modules.auth.token import create_access_token

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://arap:arap@localhost:5434/arap_test",
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
def seed(db):
    org = Org(name="CompLib Org")
    db.add(org)
    db.flush()
    user = User(
        org_id=org.id, email="user@complib.com", role="user",
        password_hash=pwd_context.hash("pw"),
    )
    db.add(user)
    db.commit()
    db.refresh(org)
    db.refresh(user)
    return {"org": org, "user": user}


@pytest.fixture
def user_token(seed):
    org = seed["org"]
    user = seed["user"]
    return create_access_token({
        "sub": str(user.id),
        "role": "user",
        "org_id": str(org.id),
    })


@pytest_asyncio.fixture
async def async_client(db, r):
    from src.main import app
    from src.database import get_db, get_redis
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: r
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

Create `services/orchestrator-api/tests/competency_library/test_crud.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_create_competency(async_client, seed, user_token):
    resp = await async_client.post(
        "/competency-library",
        json={"name": "Problem Solving", "description": "Analytical thinking", "rubric_notes": "Use STAR method"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Problem Solving"
    assert body["description"] == "Analytical thinking"
    assert "id" in body


@pytest.mark.asyncio
async def test_list_competencies(async_client, seed, user_token):
    await async_client.post(
        "/competency-library",
        json={"name": "Leadership"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp = await async_client.get(
        "/competency-library",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    names = [i["name"] for i in items]
    assert "Leadership" in names


@pytest.mark.asyncio
async def test_update_competency(async_client, seed, user_token):
    create_resp = await async_client.post(
        "/competency-library",
        json={"name": "Communication"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    comp_id = create_resp.json()["id"]
    resp = await async_client.patch(
        f"/competency-library/{comp_id}",
        json={"rubric_notes": "Updated rubric"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["rubric_notes"] == "Updated rubric"


@pytest.mark.asyncio
async def test_delete_competency(async_client, seed, user_token):
    create_resp = await async_client.post(
        "/competency-library",
        json={"name": "ToDelete"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    comp_id = create_resp.json()["id"]
    del_resp = await async_client.delete(
        f"/competency-library/{comp_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert del_resp.status_code == 204
    get_resp = await async_client.get(
        "/competency-library",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ids = [i["id"] for i in get_resp.json()]
    assert comp_id not in ids


@pytest.mark.asyncio
async def test_duplicate_name_returns_409(async_client, seed, user_token):
    await async_client.post(
        "/competency-library",
        json={"name": "Unique"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp = await async_client.post(
        "/competency-library",
        json={"name": "Unique"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(async_client):
    resp = await async_client.get("/competency-library")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd services/orchestrator-api
pytest tests/competency_library/ -v
```

Expected: multiple `404 Not Found` or `ImportError` — router not registered yet.

- [ ] **Step 3: Create schemas.py**

Create `services/orchestrator-api/src/modules/competency_library/__init__.py` (empty).

Create `services/orchestrator-api/src/modules/competency_library/schemas.py`:

```python
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CompetencyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rubric_notes: Optional[str] = None


class CompetencyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rubric_notes: Optional[str] = None


class CompetencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: Optional[str]
    rubric_notes: Optional[str]
    created_by: uuid.UUID
    created_at: datetime
```

- [ ] **Step 4: Create service.py**

Create `services/orchestrator-api/src/modules/competency_library/service.py`:

```python
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.competency_library import CompetencyLibrary
from src.modules.competency_library.schemas import CompetencyCreate, CompetencyUpdate


def list_competencies(db: Session, org_id: uuid.UUID) -> list[CompetencyLibrary]:
    return db.query(CompetencyLibrary).filter_by(org_id=org_id).all()


def create_competency(
    db: Session, org_id: uuid.UUID, user_id: uuid.UUID, data: CompetencyCreate
) -> CompetencyLibrary:
    comp = CompetencyLibrary(
        org_id=org_id,
        name=data.name,
        description=data.description,
        rubric_notes=data.rubric_notes,
        created_by=user_id,
    )
    db.add(comp)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ValueError(f"Competency '{data.name}' already exists in this org")
    db.commit()
    db.refresh(comp)
    return comp


def update_competency(
    db: Session, org_id: uuid.UUID, comp_id: uuid.UUID, data: CompetencyUpdate
) -> CompetencyLibrary:
    comp = db.query(CompetencyLibrary).filter_by(id=comp_id, org_id=org_id).first()
    if comp is None:
        raise LookupError("Competency not found")
    if data.name is not None:
        comp.name = data.name
    if data.description is not None:
        comp.description = data.description
    if data.rubric_notes is not None:
        comp.rubric_notes = data.rubric_notes
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError(f"Competency name '{data.name}' already exists in this org")
    db.refresh(comp)
    return comp


def delete_competency(db: Session, org_id: uuid.UUID, comp_id: uuid.UUID) -> None:
    comp = db.query(CompetencyLibrary).filter_by(id=comp_id, org_id=org_id).first()
    if comp is None:
        raise LookupError("Competency not found")
    db.delete(comp)
    db.commit()
```

- [ ] **Step 5: Create router.py**

Create `services/orchestrator-api/src/modules/competency_library/router.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.auth.dependencies import TokenClaims, require_user
from src.modules.competency_library import service
from src.modules.competency_library.schemas import (
    CompetencyCreate, CompetencyResponse, CompetencyUpdate,
)

router = APIRouter(prefix="/competency-library", tags=["competency-library"])


@router.get("", response_model=list[CompetencyResponse])
def list_competencies(
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    return service.list_competencies(db, claims.org_id)


@router.post("", response_model=CompetencyResponse, status_code=status.HTTP_201_CREATED)
def create_competency(
    body: CompetencyCreate,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.create_competency(db, claims.org_id, uuid.UUID(claims.sub), body)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.patch("/{comp_id}", response_model=CompetencyResponse)
def update_competency(
    comp_id: uuid.UUID,
    body: CompetencyUpdate,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.update_competency(db, claims.org_id, comp_id, body)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{comp_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_competency(
    comp_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        service.delete_competency(db, claims.org_id, comp_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 6: Register router in main.py**

Add to `services/orchestrator-api/src/main.py` (after the existing auth import line):

```python
from src.modules.competency_library.router import router as competency_library_router
```

And after `app.include_router(auth_router)`:

```python
app.include_router(competency_library_router)
```

Full `main.py` after edit:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException

from src.config import settings
from src.middleware.auth import AuthMiddleware
from src.middleware.rate_limit import RateLimitMiddleware
from src.middleware.error_handler import http_exception_handler, unhandled_exception_handler
from src.api.health import router as health_router
from src.modules.auth.router import router as auth_router
from src.modules.competency_library.router import router as competency_library_router

app = FastAPI(
    title="ARAP Orchestrator API",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(competency_library_router)
```

- [ ] **Step 7: Run tests — all 6 must pass**

```bash
cd services/orchestrator-api
pytest tests/competency_library/ -v
```

Expected:
```
PASSED tests/competency_library/test_crud.py::test_create_competency
PASSED tests/competency_library/test_crud.py::test_list_competencies
PASSED tests/competency_library/test_crud.py::test_update_competency
PASSED tests/competency_library/test_crud.py::test_delete_competency
PASSED tests/competency_library/test_crud.py::test_duplicate_name_returns_409
PASSED tests/competency_library/test_crud.py::test_unauthenticated_returns_401
```

- [ ] **Step 8: Commit**

```bash
cd D:/staging/ARAP1
git add services/orchestrator-api/src/modules/competency_library/
git add services/orchestrator-api/tests/competency_library/
git add services/orchestrator-api/src/main.py
git commit -m "[TASK-001] feat: add competency library CRUD (M1-F02)"
```

---

### Task 4: Job Assessment CRUD + weightage validation

**Files:**
- Create: `services/orchestrator-api/src/modules/job_assessments/__init__.py`
- Create: `services/orchestrator-api/src/modules/job_assessments/schemas.py`
- Create: `services/orchestrator-api/src/modules/job_assessments/service.py`
- Create: `services/orchestrator-api/src/modules/job_assessments/router.py`
- Create: `services/orchestrator-api/tests/job_assessments/__init__.py`
- Create: `services/orchestrator-api/tests/job_assessments/conftest.py`
- Create: `services/orchestrator-api/tests/job_assessments/test_crud.py`
- Create: `services/orchestrator-api/tests/job_assessments/test_weightage.py`

**Interfaces:**
- Consumes: `run_job_description_agent` from `agents.job_description.agent`.
- Produces: `create_assessment`, `get_assessment`, `list_assessments`, `update_assessment`, `delete_assessment` — used by Tasks 5 and 6.

- [ ] **Step 1: Write the conftest**

Create `services/orchestrator-api/tests/job_assessments/__init__.py` (empty).

Create `services/orchestrator-api/tests/job_assessments/conftest.py`:

```python
import os
from unittest.mock import MagicMock, patch

import fakeredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from passlib.context import CryptContext
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.models.base import Base
import src.models  # noqa: F401
from src.models.orgs import Org
from src.models.users import User
from src.modules.auth.token import create_access_token

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://arap:arap@localhost:5434/arap_test",
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
def seed(db):
    org = Org(name="JA Org")
    db.add(org)
    db.flush()
    admin = User(
        org_id=org.id, email="admin@ja.com", role="admin",
        password_hash=pwd_context.hash("pw"),
    )
    user = User(
        org_id=org.id, email="user@ja.com", role="user",
        password_hash=pwd_context.hash("pw"),
    )
    db.add_all([admin, user])
    db.commit()
    db.refresh(org); db.refresh(admin); db.refresh(user)
    return {"org": org, "admin": admin, "user": user}


@pytest.fixture
def admin_token(seed):
    return create_access_token({
        "sub": str(seed["admin"].id),
        "role": "admin",
        "org_id": str(seed["org"].id),
    })


@pytest.fixture
def user_token(seed):
    return create_access_token({
        "sub": str(seed["user"].id),
        "role": "user",
        "org_id": str(seed["org"].id),
    })


@pytest.fixture
def mock_jd_agent():
    """Prevents real Anthropic calls in job_assessment tests."""
    with patch("src.modules.job_assessments.service.run_job_description_agent") as m:
        m.return_value = None
        yield m


@pytest_asyncio.fixture
async def async_client(db, r):
    from src.main import app
    from src.database import get_db, get_redis
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: r
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


JA_BODY = {
    "title": "Backend Engineer",
    "department": "Engineering",
    "difficulty_level": "mid",
    "duration_minutes": 60,
    "required_skills": ["Python", "SQL"],
    "preferred_skills": ["Docker"],
    "behavioral_competencies": ["problem_solving", "communication"],
    "leadership_competencies": ["mentoring"],
    "competency_weightage": {"problem_solving": 50.0, "communication": 30.0, "mentoring": 20.0},
}
```

- [ ] **Step 2: Write the failing CRUD tests**

Create `services/orchestrator-api/tests/job_assessments/test_crud.py`:

```python
import pytest
from tests.job_assessments.conftest import JA_BODY


@pytest.mark.asyncio
async def test_create_assessment(async_client, seed, user_token, mock_jd_agent):
    resp = await async_client.post(
        "/job-assessments",
        json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Backend Engineer"
    assert body["difficulty_level"] == "mid"
    assert "id" in body


@pytest.mark.asyncio
async def test_list_assessments(async_client, seed, user_token, mock_jd_agent):
    await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp = await async_client.get(
        "/job-assessments",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_assessment(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]
    resp = await async_client.get(
        f"/job-assessments/{ja_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == ja_id


@pytest.mark.asyncio
async def test_update_assessment(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]
    resp = await async_client.patch(
        f"/job-assessments/{ja_id}",
        json={"title": "Senior Backend Engineer"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Senior Backend Engineer"


@pytest.mark.asyncio
async def test_delete_assessment(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]
    del_resp = await async_client.delete(
        f"/job-assessments/{ja_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_with_session_returns_409(async_client, seed, user_token, admin_token, mock_jd_agent, db):
    from src.models.candidates import Candidate
    from src.models.assessment_sessions import AssessmentSession

    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]

    candidate = Candidate(
        org_id=seed["org"].id, name="Test C", email="tc@x.com", auth_method="magic_link"
    )
    db.add(candidate)
    db.flush()
    import uuid
    session = AssessmentSession(
        org_id=seed["org"].id,
        job_assessment_id=uuid.UUID(ja_id),
        candidate_id=candidate.id,
        time_budget_seconds=3600,
    )
    db.add(session)
    db.commit()

    resp = await async_client.delete(
        f"/job-assessments/{ja_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_wrong_org_returns_404(async_client, seed, user_token, mock_jd_agent):
    import uuid
    resp = await async_client.get(
        f"/job-assessments/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(async_client):
    resp = await async_client.get("/job-assessments")
    assert resp.status_code == 401
```

- [ ] **Step 3: Write the failing weightage tests**

Create `services/orchestrator-api/tests/job_assessments/test_weightage.py`:

```python
import pytest
from tests.job_assessments.conftest import JA_BODY


@pytest.mark.asyncio
async def test_weightage_summing_to_100_passes(async_client, seed, user_token, mock_jd_agent):
    resp = await async_client.post(
        "/job-assessments",
        json={**JA_BODY, "competency_weightage": {"a": 60.0, "b": 40.0}},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_weightage_not_summing_to_100_returns_422(async_client, seed, user_token, mock_jd_agent):
    resp = await async_client.post(
        "/job-assessments",
        json={**JA_BODY, "competency_weightage": {"a": 60.0, "b": 30.0}},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 422
    assert "100" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_weightage_float_precision_passes(async_client, seed, user_token, mock_jd_agent):
    resp = await async_client.post(
        "/job-assessments",
        json={**JA_BODY, "competency_weightage": {"a": 33.33, "b": 33.33, "c": 33.34}},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_patch_weightage_validated(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]
    resp = await async_client.patch(
        f"/job-assessments/{ja_id}",
        json={"competency_weightage": {"a": 50.0}},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 422
```

- [ ] **Step 4: Run failing tests**

```bash
cd services/orchestrator-api
pytest tests/job_assessments/test_crud.py tests/job_assessments/test_weightage.py -v
```

Expected: all fail with `404 Not Found` — router not registered.

- [ ] **Step 5: Create schemas.py**

Create `services/orchestrator-api/src/modules/job_assessments/__init__.py` (empty).

Create `services/orchestrator-api/src/modules/job_assessments/schemas.py`:

```python
import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator


def _validate_weightage(v: dict[str, float]) -> dict[str, float]:
    if v and abs(sum(v.values()) - 100) > 0.01:
        raise ValueError("competency_weightage must sum to 100")
    return v


class JobAssessmentCreate(BaseModel):
    title: str
    department: Optional[str] = None
    experience_min: Optional[int] = None
    experience_max: Optional[int] = None
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    responsibilities: Optional[str] = None
    education: Optional[str] = None
    certifications: list[str] = []
    behavioral_competencies: list[str] = []
    leadership_competencies: list[str] = []
    culture_values: list[str] = []
    difficulty_level: Literal["junior", "mid", "senior", "executive"]
    duration_minutes: int
    competency_weightage: dict[str, float]
    is_template: bool = False
    role_family: Optional[str] = None

    @field_validator("competency_weightage")
    @classmethod
    def weightage_sums_to_100(cls, v: dict[str, float]) -> dict[str, float]:
        return _validate_weightage(v)


class JobAssessmentUpdate(BaseModel):
    title: Optional[str] = None
    department: Optional[str] = None
    experience_min: Optional[int] = None
    experience_max: Optional[int] = None
    required_skills: Optional[list[str]] = None
    preferred_skills: Optional[list[str]] = None
    responsibilities: Optional[str] = None
    education: Optional[str] = None
    certifications: Optional[list[str]] = None
    behavioral_competencies: Optional[list[str]] = None
    leadership_competencies: Optional[list[str]] = None
    culture_values: Optional[list[str]] = None
    difficulty_level: Optional[Literal["junior", "mid", "senior", "executive"]] = None
    duration_minutes: Optional[int] = None
    competency_weightage: Optional[dict[str, float]] = None
    is_template: Optional[bool] = None
    role_family: Optional[str] = None

    @field_validator("competency_weightage")
    @classmethod
    def weightage_sums_to_100(cls, v: Optional[dict[str, float]]) -> Optional[dict[str, float]]:
        if v is not None:
            return _validate_weightage(v)
        return v


class CloneRequest(BaseModel):
    competency_weightage: Optional[dict[str, float]] = None
    required_skills: Optional[list[str]] = None
    preferred_skills: Optional[list[str]] = None
    role_family: Optional[str] = None

    @field_validator("competency_weightage")
    @classmethod
    def weightage_sums_to_100(cls, v: Optional[dict[str, float]]) -> Optional[dict[str, float]]:
        if v is not None:
            return _validate_weightage(v)
        return v


class InviteRequest(BaseModel):
    candidate_name: str
    candidate_email: str
    time_budget_seconds: int


class InviteResponse(BaseModel):
    assessment_session_id: uuid.UUID
    candidate_id: uuid.UUID
    status: str


class JobAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    title: str
    department: Optional[str]
    experience_min: Optional[int]
    experience_max: Optional[int]
    required_skills: list[str]
    preferred_skills: list[str]
    responsibilities: Optional[str]
    education: Optional[str]
    certifications: list[str]
    behavioral_competencies: list[str]
    leadership_competencies: list[str]
    culture_values: list[str]
    difficulty_level: str
    duration_minutes: int
    competency_weightage: dict
    is_template: bool
    role_family: Optional[str]
    job_profile: Optional[dict]
    created_by: uuid.UUID
    created_at: datetime
```

- [ ] **Step 6: Create service.py**

Create `services/orchestrator-api/src/modules/job_assessments/service.py`:

```python
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from agents.job_description.agent import run_job_description_agent
from src.models.assessment_sessions import AssessmentSession
from src.models.candidates import Candidate
from src.models.job_assessments import JobAssessment
from src.modules.job_assessments.schemas import (
    CloneRequest, InviteRequest, InviteResponse,
    JobAssessmentCreate, JobAssessmentUpdate,
)


def list_assessments(
    db: Session, org_id: uuid.UUID, is_template: Optional[bool] = None
) -> list[JobAssessment]:
    q = db.query(JobAssessment).filter_by(org_id=org_id)
    if is_template is not None:
        q = q.filter(JobAssessment.is_template == is_template)
    return q.all()


def get_assessment(db: Session, org_id: uuid.UUID, assessment_id: uuid.UUID) -> JobAssessment:
    row = db.query(JobAssessment).filter_by(id=assessment_id, org_id=org_id).first()
    if row is None:
        raise LookupError("Job assessment not found")
    return row


def create_assessment(
    db: Session, org_id: uuid.UUID, user_id: uuid.UUID, data: JobAssessmentCreate
) -> JobAssessment:
    row = JobAssessment(
        org_id=org_id,
        title=data.title,
        department=data.department,
        experience_min=data.experience_min,
        experience_max=data.experience_max,
        required_skills=data.required_skills,
        preferred_skills=data.preferred_skills,
        responsibilities=data.responsibilities,
        education=data.education,
        certifications=data.certifications,
        behavioral_competencies=data.behavioral_competencies,
        leadership_competencies=data.leadership_competencies,
        culture_values=data.culture_values,
        difficulty_level=data.difficulty_level,
        duration_minutes=data.duration_minutes,
        competency_weightage=data.competency_weightage,
        is_template=data.is_template,
        role_family=data.role_family,
        created_by=user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    run_job_description_agent(db, row)
    db.refresh(row)
    return row


def update_assessment(
    db: Session, org_id: uuid.UUID, assessment_id: uuid.UUID, data: JobAssessmentUpdate
) -> JobAssessment:
    row = get_assessment(db, org_id, assessment_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    run_job_description_agent(db, row)
    db.refresh(row)
    return row


def delete_assessment(db: Session, org_id: uuid.UUID, assessment_id: uuid.UUID) -> None:
    row = get_assessment(db, org_id, assessment_id)
    has_sessions = db.query(AssessmentSession).filter_by(
        job_assessment_id=assessment_id
    ).first() is not None
    if has_sessions:
        raise PermissionError("Cannot delete assessment with existing sessions")
    db.delete(row)
    db.commit()


def clone_assessment(
    db: Session, org_id: uuid.UUID, user_id: uuid.UUID,
    assessment_id: uuid.UUID, overrides: CloneRequest,
) -> JobAssessment:
    source = get_assessment(db, org_id, assessment_id)
    clone = JobAssessment(
        org_id=org_id,
        title=source.title,
        department=source.department,
        experience_min=source.experience_min,
        experience_max=source.experience_max,
        required_skills=overrides.required_skills if overrides.required_skills is not None else list(source.required_skills),
        preferred_skills=overrides.preferred_skills if overrides.preferred_skills is not None else list(source.preferred_skills),
        responsibilities=source.responsibilities,
        education=source.education,
        certifications=list(source.certifications),
        behavioral_competencies=list(source.behavioral_competencies),
        leadership_competencies=list(source.leadership_competencies),
        culture_values=list(source.culture_values),
        difficulty_level=source.difficulty_level,
        duration_minutes=source.duration_minutes,
        competency_weightage=overrides.competency_weightage if overrides.competency_weightage is not None else dict(source.competency_weightage),
        is_template=False,
        role_family=overrides.role_family if overrides.role_family is not None else source.role_family,
        created_by=user_id,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    run_job_description_agent(db, clone)
    db.refresh(clone)
    return clone


def invite_candidate(
    db: Session, org_id: uuid.UUID, assessment_id: uuid.UUID,
    user_id: uuid.UUID, data: InviteRequest,
) -> InviteResponse:
    get_assessment(db, org_id, assessment_id)

    candidate = db.query(Candidate).filter_by(
        org_id=org_id, email=data.candidate_email
    ).first()
    if candidate is None:
        candidate = Candidate(
            org_id=org_id,
            name=data.candidate_name,
            email=data.candidate_email,
            auth_method="magic_link",
        )
        db.add(candidate)
        db.flush()

    session = AssessmentSession(
        org_id=org_id,
        job_assessment_id=assessment_id,
        candidate_id=candidate.id,
        time_budget_seconds=data.time_budget_seconds,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return InviteResponse(
        assessment_session_id=session.id,
        candidate_id=candidate.id,
        status=session.status,
    )
```

- [ ] **Step 7: Create router.py**

Create `services/orchestrator-api/src/modules/job_assessments/router.py`:

```python
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.auth.dependencies import TokenClaims, require_user
from src.modules.job_assessments import service
from src.modules.job_assessments.schemas import (
    CloneRequest, InviteRequest, InviteResponse,
    JobAssessmentCreate, JobAssessmentResponse, JobAssessmentUpdate,
)

router = APIRouter(prefix="/job-assessments", tags=["job-assessments"])


@router.get("", response_model=list[JobAssessmentResponse])
def list_assessments(
    is_template: Optional[bool] = Query(default=None),
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    return service.list_assessments(db, claims.org_id, is_template)


@router.post("", response_model=JobAssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_assessment(
    body: JobAssessmentCreate,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    return service.create_assessment(db, claims.org_id, uuid.UUID(claims.sub), body)


@router.get("/{assessment_id}", response_model=JobAssessmentResponse)
def get_assessment(
    assessment_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.get_assessment(db, claims.org_id, assessment_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{assessment_id}", response_model=JobAssessmentResponse)
def update_assessment(
    assessment_id: uuid.UUID,
    body: JobAssessmentUpdate,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.update_assessment(db, claims.org_id, assessment_id, body)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assessment(
    assessment_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        service.delete_assessment(db, claims.org_id, assessment_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/{assessment_id}/clone", response_model=JobAssessmentResponse, status_code=status.HTTP_201_CREATED)
def clone_assessment(
    assessment_id: uuid.UUID,
    body: CloneRequest = CloneRequest(),
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.clone_assessment(db, claims.org_id, uuid.UUID(claims.sub), assessment_id, body)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{assessment_id}/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def invite_candidate(
    assessment_id: uuid.UUID,
    body: InviteRequest,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.invite_candidate(db, claims.org_id, assessment_id, uuid.UUID(claims.sub), body)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 8: Add router to main.py**

Add to `services/orchestrator-api/src/main.py`:

```python
from src.modules.job_assessments.router import router as job_assessments_router
```

And `app.include_router(job_assessments_router)` after the competency_library line.

Full updated `main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException

from src.config import settings
from src.middleware.auth import AuthMiddleware
from src.middleware.rate_limit import RateLimitMiddleware
from src.middleware.error_handler import http_exception_handler, unhandled_exception_handler
from src.api.health import router as health_router
from src.modules.auth.router import router as auth_router
from src.modules.competency_library.router import router as competency_library_router
from src.modules.job_assessments.router import router as job_assessments_router

app = FastAPI(
    title="ARAP Orchestrator API",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(competency_library_router)
app.include_router(job_assessments_router)
```

- [ ] **Step 9: Run all job_assessment tests**

```bash
cd services/orchestrator-api
pytest tests/job_assessments/test_crud.py tests/job_assessments/test_weightage.py -v
```

Expected: all 12 tests pass.

- [ ] **Step 10: Commit**

```bash
cd D:/staging/ARAP1
git add services/orchestrator-api/src/modules/job_assessments/
git add services/orchestrator-api/tests/job_assessments/
git add services/orchestrator-api/src/main.py
git commit -m "[TASK-001] feat: add job assessment CRUD + weightage validation (M1-F01)"
```

---

### Task 5: Templates & Clone

**Files:**
- Create: `services/orchestrator-api/tests/job_assessments/test_templates.py`

(service.py and router.py already have `clone_assessment` and `is_template` filter from Task 4 — tests were the only missing piece.)

**Interfaces:**
- Consumes: `clone_assessment`, `list_assessments(is_template=...)` from Task 4.

- [ ] **Step 1: Write the failing template tests**

Create `services/orchestrator-api/tests/job_assessments/test_templates.py`:

```python
import pytest
from tests.job_assessments.conftest import JA_BODY

TEMPLATE_BODY = {**JA_BODY, "is_template": True, "role_family": "engineering"}


@pytest.mark.asyncio
async def test_create_template(async_client, seed, user_token, mock_jd_agent):
    resp = await async_client.post(
        "/job-assessments",
        json=TEMPLATE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_template"] is True
    assert body["role_family"] == "engineering"


@pytest.mark.asyncio
async def test_list_templates_filter(async_client, seed, user_token, mock_jd_agent):
    # Create one template and one regular
    await async_client.post(
        "/job-assessments", json=TEMPLATE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    await async_client.post(
        "/job-assessments", json={**JA_BODY, "is_template": False},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp = await async_client.get(
        "/job-assessments?is_template=true",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert all(i["is_template"] is True for i in items)


@pytest.mark.asyncio
async def test_clone_copies_all_fields(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=TEMPLATE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    source_id = create_resp.json()["id"]

    clone_resp = await async_client.post(
        f"/job-assessments/{source_id}/clone",
        json={},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert clone_resp.status_code == 201
    clone = clone_resp.json()
    assert clone["id"] != source_id
    assert clone["title"] == "Backend Engineer"
    assert clone["is_template"] is False


@pytest.mark.asyncio
async def test_clone_with_weightage_override(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=TEMPLATE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    source_id = create_resp.json()["id"]

    new_weightage = {"problem_solving": 70.0, "communication": 20.0, "mentoring": 10.0}
    clone_resp = await async_client.post(
        f"/job-assessments/{source_id}/clone",
        json={"competency_weightage": new_weightage},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert clone_resp.status_code == 201
    assert clone_resp.json()["competency_weightage"] == new_weightage


@pytest.mark.asyncio
async def test_clone_invalid_weightage_override_returns_422(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=TEMPLATE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    source_id = create_resp.json()["id"]

    clone_resp = await async_client.post(
        f"/job-assessments/{source_id}/clone",
        json={"competency_weightage": {"a": 50.0}},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert clone_resp.status_code == 422


@pytest.mark.asyncio
async def test_clone_nonexistent_returns_404(async_client, seed, user_token, mock_jd_agent):
    import uuid
    resp = await async_client.post(
        f"/job-assessments/{uuid.uuid4()}/clone",
        json={},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run the tests**

```bash
cd services/orchestrator-api
pytest tests/job_assessments/test_templates.py -v
```

Expected: all 6 pass (implementation was already in service.py from Task 4).

- [ ] **Step 3: Commit**

```bash
cd D:/staging/ARAP1
git add services/orchestrator-api/tests/job_assessments/test_templates.py
git commit -m "[TASK-001] test: add template and clone tests (M1-F03)"
```

---

### Task 6: Candidate Invitation

**Files:**
- Create: `services/orchestrator-api/tests/job_assessments/test_invite.py`

(service.py and router.py already have `invite_candidate` from Task 4.)

**Interfaces:**
- Consumes: `invite_candidate` from Task 4 service.

- [ ] **Step 1: Write the failing invite tests**

Create `services/orchestrator-api/tests/job_assessments/test_invite.py`:

```python
import pytest
from tests.job_assessments.conftest import JA_BODY

INVITE_BODY = {
    "candidate_name": "Alice Smith",
    "candidate_email": "alice@candidate.com",
    "time_budget_seconds": 3600,
}


@pytest.mark.asyncio
async def test_invite_creates_assessment_session(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]

    resp = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json=INVITE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "assessment_session_id" in body
    assert "candidate_id" in body
    assert body["status"] == "invited"


@pytest.mark.asyncio
async def test_invite_upserts_candidate_by_email(async_client, seed, user_token, mock_jd_agent, db):
    from src.models.candidates import Candidate

    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]

    # First invite — creates candidate
    resp1 = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json={**INVITE_BODY, "candidate_email": "bob@candidate.com"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    cand_id_1 = resp1.json()["candidate_id"]

    # Second invite same email — reuses candidate
    resp2 = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json={**INVITE_BODY, "candidate_email": "bob@candidate.com"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    cand_id_2 = resp2.json()["candidate_id"]

    assert cand_id_1 == cand_id_2

    count = db.query(Candidate).filter_by(
        org_id=seed["org"].id, email="bob@candidate.com"
    ).count()
    assert count == 1


@pytest.mark.asyncio
async def test_invite_creates_distinct_sessions(async_client, seed, user_token, mock_jd_agent):
    create_resp = await async_client.post(
        "/job-assessments", json=JA_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    ja_id = create_resp.json()["id"]

    resp1 = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json={**INVITE_BODY, "candidate_email": "c1@x.com"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp2 = await async_client.post(
        f"/job-assessments/{ja_id}/invite",
        json={**INVITE_BODY, "candidate_email": "c2@x.com"},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert resp1.json()["assessment_session_id"] != resp2.json()["assessment_session_id"]


@pytest.mark.asyncio
async def test_invite_bad_assessment_id_returns_404(async_client, seed, user_token, mock_jd_agent):
    import uuid
    resp = await async_client.post(
        f"/job-assessments/{uuid.uuid4()}/invite",
        json=INVITE_BODY,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run the tests**

```bash
cd services/orchestrator-api
pytest tests/job_assessments/test_invite.py -v
```

Expected: all 4 pass.

- [ ] **Step 3: Run the full test suite to check for regressions**

```bash
cd services/orchestrator-api
pytest -v
```

Expected: all tests pass (existing auth/model tests + new tests).

- [ ] **Step 4: Commit**

```bash
cd D:/staging/ARAP1
git add services/orchestrator-api/tests/job_assessments/test_invite.py
git commit -m "[TASK-001] feat: candidate invitation creates assessment_session 1:1:1 (M1-F04)"
```

---

### Task 7: Full suite run + session file update

**Files:**
- Modify: `arap-sessions.ps1` (mark `job-assessment` session complete; point to next session)

- [ ] **Step 1: Run the complete test suite**

```bash
cd services/orchestrator-api
pytest -v --tb=short
```

Expected: all tests pass. Count should include: prior auth + model tests + new job_assessments + competency_library + job_description tests.

- [ ] **Step 2: Verify API boots cleanly**

```bash
cd services/orchestrator-api
uvicorn src.main:app --port 8000 --reload
```

Expected: server starts, no import errors. Visit `http://localhost:8000/docs` — should show job-assessments and competency-library route groups.

- [ ] **Step 3: Mark session complete in arap-sessions.ps1**

In `arap-sessions.ps1`, replace the `job-assessment` session prompt block:

```powershell
"job-assessment" = @{
    model = $SONNET
    task  = "TASK-001"
    label = "Phase 1 . Job Assessment Builder (M1) [COMPLETE]"
    prompt = @'
*** SESSION COMPLETE — DO NOT RE-RUN ***
M1 (F01-F04) fully implemented and reviewed.
What was built:
  - migrations/versions/0002: is_template, role_family, job_profile columns on job_assessments
  - agents/job_description/prompts.py + agent.py: Haiku structured output via tool_use; non-fatal on API error
  - src/modules/competency_library/: CRUD, unique-per-org constraint, 409 on duplicate
  - src/modules/job_assessments/: CRUD, weightage validation (sum=100 ±0.01), templates flag+filter, clone with overrides, candidate invite (upsert candidate + assessment_session)
  - All endpoints: require_user (role user or admin); org_id from JWT claims
  - pytest PYTHONPATH = [".", "../.."] enables agents/ import from service tests

Key decisions:
  - JD agent called synchronously post-create/update; failure leaves job_profile=NULL (non-fatal)
  - Template = is_template bool on job_assessments (no separate table)
  - Invite upserts candidate on (org_id, email); creates fresh assessment_session each call
  - DELETE guarded: 409 if any assessment_session exists for the assessment

Next session: .\arap-sessions.ps1 -Session resume-ingestion
'@
}
```

- [ ] **Step 4: Commit**

```bash
cd D:/staging/ARAP1
git add arap-sessions.ps1
git commit -m "[TASK-001] chore: mark job-assessment session complete in session launcher"
```

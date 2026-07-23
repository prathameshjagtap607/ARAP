# Resume & Profile Ingestion (M2-F01–F04) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `services/ingestion-service` + `agents/resume_analysis` to parse resumes (PDF/DOCX/text), enrich from GitHub, compute a resume-to-JD match score, and write a `candidate_profiles` row with per-field confidence scores.

**Architecture:** Sync-first FastAPI service at port 8001; files stored in MinIO (S3-compatible); Resume Analysis Agent uses Claude Sonnet tool_use for structured extraction; cosine similarity of OpenAI embeddings drives the match score. Files > 5 MB or parse time > 8 s get a `202 Accepted` with asyncio background continuation.

**Tech Stack:** FastAPI, SQLAlchemy 2.x (sync), psycopg (binary), pypdf, python-docx, boto3, anthropic, openai, httpx, moto (test mocking), pytest.

## Global Constraints

- Python ≥ 3.11 everywhere.
- SQLAlchemy sync (not async) — matches orchestrator-api pattern; no asyncio DB sessions.
- All DB writes org-scoped; every `candidate_profiles` insert carries `org_id`.
- Agent errors are non-fatal: log + leave `parsing_confidence = NULL`; endpoint still returns 200.
- GitHub enrichment is additive only; 404 or rate-limit → `github_enrichment = NULL`, continue.
- Embedding model: `text-embedding-3-small` (OpenAI), `vector(1536)` — do not change dimension.
- No Alembic in ingestion-service; schema managed by orchestrator-api migrations only.
- Test DB: `postgresql://arap:arap@localhost:5434/arap_test` (port 5434, same as orchestrator-api tests).
- Never commit `.env` files; update `.env.example` files only.
- Commit format: `[TASK-001] <type>: <what changed>`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `services/orchestrator-api/migrations/versions/0003_resume_ingestion.py` | Create | Add `field_confidence`, `match_score`, `github_enrichment` columns + unique constraint to `candidate_profiles` |
| `services/orchestrator-api/src/models/candidate_profiles.py` | Modify | Add 3 new mapped columns + unique constraint |
| `services/orchestrator-api/src/config.py` | Modify | Add `OPENAI_API_KEY`, `INGESTION_SERVICE_URL` |
| `docker-compose.yml` | Modify | Add `minio` service + `minio-data` volume + `ingestion-service` service |
| `services/ingestion-service/pyproject.toml` | Modify | Add all runtime + dev dependencies |
| `services/ingestion-service/src/__init__.py` | Create | Empty package marker |
| `services/ingestion-service/src/config.py` | Create | `Settings` (pydantic-settings) for ingestion-service |
| `services/ingestion-service/src/database.py` | Create | Engine + `SessionLocal` + `get_db()` |
| `services/ingestion-service/src/models.py` | Create | Minimal SA models: `Org`, `Candidate`, `JobAssessment`, `CandidateProfile` |
| `services/ingestion-service/src/s3.py` | Create | `upload_file()`, `download_file()`, `ensure_bucket()` |
| `services/ingestion-service/src/parsers.py` | Create | `extract_text(bytes, mime) -> str` |
| `services/ingestion-service/src/embeddings.py` | Create | `embed(text) -> list[float]`, `cosine_similarity()` |
| `services/ingestion-service/src/routers/__init__.py` | Create | Empty |
| `services/ingestion-service/src/routers/health.py` | Create | `GET /health` |
| `services/ingestion-service/src/routers/upload.py` | Create | `POST /upload` — multipart → S3 |
| `services/ingestion-service/src/routers/analyze.py` | Create | `POST /analyze`, `GET /analyze/{candidate_id}/{job_assessment_id}` |
| `services/ingestion-service/src/main.py` | Modify | Wire all routers, startup bucket creation |
| `agents/resume_analysis/__init__.py` | Modify | Empty (already exists) |
| `agents/resume_analysis/prompts.py` | Create | `SYSTEM_PROMPT`, `RESUME_EXTRACTION_TOOL` |
| `agents/resume_analysis/agent.py` | Create | `run_resume_analysis_agent(raw_text, job_profile) -> dict \| None` |
| `services/ingestion-service/tests/__init__.py` | Create | Empty |
| `services/ingestion-service/tests/conftest.py` | Create | DB engine, S3 mock, sample fixtures, mock clients |
| `services/ingestion-service/tests/test_parsers.py` | Create | Parser unit tests |
| `services/ingestion-service/tests/test_s3.py` | Create | S3 upload/download tests (moto) |
| `services/ingestion-service/tests/test_upload.py` | Create | `POST /upload` integration tests |
| `services/ingestion-service/tests/test_analyze.py` | Create | `POST /analyze` sync pipeline tests |
| `services/ingestion-service/tests/test_analyze_async.py` | Create | Large-doc 202 + GET polling tests |
| `services/ingestion-service/tests/test_github.py` | Create | GitHub enrichment happy path + 404 |
| `agents/resume_analysis/tests/__init__.py` | Create | Empty |
| `agents/resume_analysis/tests/test_agent.py` | Create | Agent tool_use shape + non-fatal error |

---

## Task 1: Migration 0003 + SA Model Update

**Files:**
- Create: `services/orchestrator-api/migrations/versions/0003_resume_ingestion.py`
- Modify: `services/orchestrator-api/src/models/candidate_profiles.py`

**Interfaces:**
- Produces: `CandidateProfile.field_confidence`, `.match_score`, `.github_enrichment` columns usable by Tasks 8–9.

- [ ] **Step 1: Write the migration**

Create `services/orchestrator-api/migrations/versions/0003_resume_ingestion.py`:

```python
"""add field_confidence match_score github_enrichment to candidate_profiles

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column("field_confidence", JSONB(), nullable=True),
    )
    op.add_column(
        "candidate_profiles",
        sa.Column("match_score", sa.Numeric(4, 3), nullable=True),
    )
    op.add_column(
        "candidate_profiles",
        sa.Column("github_enrichment", JSONB(), nullable=True),
    )
    op.create_check_constraint(
        "ck_candidate_profiles_match_score",
        "candidate_profiles",
        "match_score IS NULL OR match_score BETWEEN 0 AND 1",
    )
    op.create_unique_constraint(
        "uq_candidate_profiles_candidate_job",
        "candidate_profiles",
        ["candidate_id", "job_assessment_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_candidate_profiles_candidate_job", "candidate_profiles", type_="unique")
    op.drop_constraint("ck_candidate_profiles_match_score", "candidate_profiles")
    op.drop_column("candidate_profiles", "github_enrichment")
    op.drop_column("candidate_profiles", "match_score")
    op.drop_column("candidate_profiles", "field_confidence")
```

- [ ] **Step 2: Update the SA model**

Replace `services/orchestrator-api/src/models/candidate_profiles.py` in full:

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    __table_args__ = (
        CheckConstraint("parsing_confidence BETWEEN 0 AND 1", name="ck_candidate_profiles_parsing_confidence"),
        CheckConstraint(
            "match_score IS NULL OR match_score BETWEEN 0 AND 1",
            name="ck_candidate_profiles_match_score",
        ),
        UniqueConstraint("candidate_id", "job_assessment_id", name="uq_candidate_profiles_candidate_job"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    job_assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_assessments.id"), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    skill_matrix: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    experience_matrix: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    leadership_level_estimate: Mapped[Optional[str]] = mapped_column(String)
    strengths: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    risk_flags: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    parsing_confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))
    field_confidence: Mapped[Optional[dict]] = mapped_column(JSONB)
    match_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))
    github_enrichment: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 3: Run migration against dev DB**

```bash
cd services/orchestrator-api
alembic upgrade head
```

Expected output ends with: `Running upgrade 0002 -> 0003, add field_confidence match_score github_enrichment to candidate_profiles`

- [ ] **Step 4: Verify orchestrator-api tests still pass**

```bash
cd services/orchestrator-api
pytest tests/ -x -q
```

Expected: all tests pass (no new columns touched by existing tests).

- [ ] **Step 5: Commit**

```bash
git add services/orchestrator-api/migrations/versions/0003_resume_ingestion.py \
        services/orchestrator-api/src/models/candidate_profiles.py
git commit -m "[TASK-001] feat: migration 0003 — field_confidence, match_score, github_enrichment on candidate_profiles"
```

---

## Task 2: docker-compose + env Updates

**Files:**
- Modify: `docker-compose.yml`
- Modify: `services/orchestrator-api/src/config.py`

**Interfaces:**
- Produces: `OPENAI_API_KEY` and `INGESTION_SERVICE_URL` available in orchestrator-api settings; MinIO reachable at `http://minio:9000` inside Docker network, `http://localhost:9000` locally.

- [ ] **Step 1: Add MinIO + ingestion-service to docker-compose.yml**

In `docker-compose.yml`, add inside `services:` (after `redis:`):

```yaml
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: arap
      MINIO_ROOT_PASSWORD: arap_secret
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio-data:/var/lib/minio/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      timeout: 5s
      retries: 5

  ingestion-service:
    build:
      context: services/ingestion-service
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://arap:arap@db-dev:5432/arap_dev
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      S3_ENDPOINT_URL: http://minio:9000
      S3_ACCESS_KEY: arap
      S3_SECRET_KEY: arap_secret
      S3_BUCKET_RESUMES: arap-resumes
    ports:
      - "8001:8001"
    depends_on:
      db-dev:
        condition: service_healthy
      minio:
        condition: service_healthy
    profiles:
      - full
```

Add `minio-data:` under `volumes:` (alongside `pgdata-dev:` and `pgdata-test:`):

```yaml
volumes:
  pgdata-dev:
  pgdata-test:
  minio-data:
```

- [ ] **Step 2: Update orchestrator-api config**

In `services/orchestrator-api/src/config.py`, add after `ANTHROPIC_API_KEY`:

```python
    OPENAI_API_KEY: str
    INGESTION_SERVICE_URL: str = "http://localhost:8001"
```

- [ ] **Step 3: Verify docker-compose parses cleanly**

```bash
docker compose config --quiet
```

Expected: exits 0 with no errors.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml services/orchestrator-api/src/config.py
git commit -m "[TASK-001] chore: add minio + ingestion-service to docker-compose; OPENAI_API_KEY in config"
```

---

## Task 3: ingestion-service Scaffold (pyproject, config, database, models)

**Files:**
- Modify: `services/ingestion-service/pyproject.toml`
- Create: `services/ingestion-service/src/__init__.py`
- Create: `services/ingestion-service/src/config.py`
- Create: `services/ingestion-service/src/database.py`
- Create: `services/ingestion-service/src/models.py`
- Create: `services/ingestion-service/tests/__init__.py`
- Create: `services/ingestion-service/tests/conftest.py`

**Interfaces:**
- Produces:
  - `settings` (config.py) — all env vars consumed by later tasks
  - `get_db()` (database.py) — sync SQLAlchemy session generator
  - `Candidate`, `JobAssessment`, `CandidateProfile`, `Org` SA models (models.py)
  - `engine`, `Base` (database.py) — used by test conftest

- [ ] **Step 1: Update pyproject.toml**

Replace `services/ingestion-service/pyproject.toml` in full:

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
    "pypdf>=4.0",
    "python-docx>=1.1",
    "httpx>=0.27",
    "boto3>=1.34",
    "anthropic>=0.28",
    "sqlalchemy>=2.0",
    "psycopg[binary]>=3.1",
    "openai>=1.30",
    "pydantic-settings>=2.0",
    "numpy>=1.26",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "moto[s3]>=5.0",
    "fakeredis>=2.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.setuptools.packages.find]
where = ["."]
include = ["src*"]
```

- [ ] **Step 2: Install dependencies**

```bash
cd services/ingestion-service
pip install -e ".[dev]"
```

Expected: installs without errors.

- [ ] **Step 3: Create `src/__init__.py`**

```python
```
(empty file)

- [ ] **Step 4: Create `src/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql://arap:arap@localhost:5433/arap_dev"
    ANTHROPIC_API_KEY: str
    OPENAI_API_KEY: str
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "arap"
    S3_SECRET_KEY: str = "arap_secret"
    S3_BUCKET_RESUMES: str = "arap-resumes"
    LARGE_DOC_BYTES: int = 5_242_880
    LARGE_DOC_PARSE_TIMEOUT: float = 8.0


settings = Settings()
```

- [ ] **Step 5: Create `src/database.py`**

```python
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 6: Create `src/models.py`**

Minimal SA models for the 4 tables this service reads/writes. Mirrors column names from orchestrator-api but defined independently (no shared Base import across services).

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    plan_tier: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'trial'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        UniqueConstraint("org_id", "email", name="uq_candidates_org_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    resume_file_url: Mapped[Optional[str]] = mapped_column(Text)
    linkedin_url: Mapped[Optional[str]] = mapped_column(Text)
    github_url: Mapped[Optional[str]] = mapped_column(Text)
    portfolio_url: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class JobAssessment(Base):
    __tablename__ = "job_assessments"
    __table_args__ = (
        CheckConstraint(
            "difficulty_level IN ('junior','mid','senior','executive')",
            name="ck_job_assessments_difficulty_level",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    required_skills: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    preferred_skills: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    difficulty_level: Mapped[str] = mapped_column(String, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    competency_weightage: Mapped[dict] = mapped_column(JSONB, nullable=False)
    job_profile: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    __table_args__ = (
        CheckConstraint("parsing_confidence BETWEEN 0 AND 1", name="ck_candidate_profiles_parsing_confidence"),
        CheckConstraint(
            "match_score IS NULL OR match_score BETWEEN 0 AND 1",
            name="ck_candidate_profiles_match_score",
        ),
        UniqueConstraint("candidate_id", "job_assessment_id", name="uq_candidate_profiles_candidate_job"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    job_assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_assessments.id"), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    skill_matrix: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    experience_matrix: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    leadership_level_estimate: Mapped[Optional[str]] = mapped_column(String)
    strengths: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    risk_flags: Mapped[list] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    parsing_confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))
    field_confidence: Mapped[Optional[dict]] = mapped_column(JSONB)
    match_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))
    github_enrichment: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

- [ ] **Step 7: Create `tests/__init__.py`**

Empty file.

- [ ] **Step 8: Create `tests/conftest.py`**

```python
import io
import os
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.database import get_db
from src.models import Base, Candidate, CandidateProfile, JobAssessment, Org

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://arap:arap@localhost:5434/arap_test",
)

SAMPLE_PDF_BYTES = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
    b"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
    b"4 0 obj<</Length 60>>stream\nBT /F1 12 Tf 100 700 Td "
    b"(John Doe Python Developer 5 years experience) Tj ET\nendstream\nendobj\n"
    b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"xref\n0 6\n0000000000 65535 f\n0000000009 00000 n\n"
    b"0000000058 00000 n\n0000000115 00000 n\n0000000266 00000 n\n"
    b"0000000380 00000 n\ntrailer<</Size 6/Root 1 0 R>>\nstartxref\n456\n%%EOF"
)

SAMPLE_DOCX_TEXT = "John Doe\nPython Developer\n5 years experience\nSkills: Python, FastAPI, PostgreSQL"

MOCK_AGENT_OUTPUT = {
    "skills": {"explicit": ["Python", "FastAPI"], "inferred": ["REST APIs"]},
    "projects": [{"name": "API Service", "tech": ["Python"], "description": "Built REST API"}],
    "tech_used": ["PostgreSQL", "Redis"],
    "employment_history": [
        {"company": "TechCorp", "title": "Developer", "start": "2020-01",
         "end": "2025-01", "team_size": 5, "scope": "regional", "key_achievements": ["Improved latency"]}
    ],
    "education": [{"degree": "B.Tech", "field": "CS", "institution": "MIT", "year": 2019}],
    "certifications": [],
    "achievements": ["Reduced API latency by 40%"],
    "leadership_indicators": {"max_team_size": 5, "scope": "regional", "budget_ownership": None},
    "career_timeline": {"total_years": 5.0, "job_count": 1, "gaps": []},
    "domain_keywords": ["backend", "microservices"],
    "field_confidence": {
        "skills": 0.92, "projects": 0.85, "tech_used": 0.90,
        "employment_history": 0.95, "education": 0.97, "certifications": 0.80,
        "achievements": 0.75, "leadership_indicators": 0.70,
        "career_timeline": 0.88, "domain_keywords": 0.83,
    },
}

MOCK_EMBEDDING = [0.1] * 1536


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
def seed(db):
    org = Org(name="Test Org")
    db.add(org)
    db.flush()
    candidate = Candidate(
        org_id=org.id, name="John Doe", email="john@example.com",
        resume_file_url=None, github_url=None,
    )
    db.add(candidate)
    db.flush()
    job = JobAssessment(
        org_id=org.id, title="Backend Engineer",
        required_skills=["Python", "FastAPI"],
        preferred_skills=["Docker"],
        difficulty_level="mid", duration_minutes=60,
        competency_weightage={"problem_solving": 100.0},
        job_profile={
            "required_skills": ["Python", "FastAPI"],
            "preferred_skills": ["Docker"],
        },
        created_by=org.id,
    )
    db.add(job)
    db.commit()
    db.refresh(org); db.refresh(candidate); db.refresh(job)
    return {"org": org, "candidate": candidate, "job": job}


@pytest.fixture
def client(db):
    from src.main import app
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_s3(tmp_path):
    """In-memory S3 mock using moto."""
    import boto3
    from moto import mock_aws

    with mock_aws():
        s3 = boto3.client(
            "s3",
            endpoint_url=None,
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        s3.create_bucket(Bucket="arap-resumes")
        yield s3


@pytest.fixture
def mock_agent():
    with patch("src.routers.analyze.run_resume_analysis_agent", return_value=MOCK_AGENT_OUTPUT) as m:
        yield m


@pytest.fixture
def mock_embed():
    with patch("src.routers.analyze.embed", return_value=MOCK_EMBEDDING) as m:
        yield m
```

- [ ] **Step 9: Verify the test infrastructure imports cleanly**

```bash
cd services/ingestion-service
python -c "from tests.conftest import MOCK_AGENT_OUTPUT; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 10: Commit**

```bash
git add services/ingestion-service/
git commit -m "[TASK-001] feat: ingestion-service scaffold — pyproject, config, database, models, test conftest"
```

---

## Task 4: `parsers.py` (TDD)

**Files:**
- Create: `services/ingestion-service/src/parsers.py`
- Create: `services/ingestion-service/tests/test_parsers.py`

**Interfaces:**
- Produces: `extract_text(file_bytes: bytes, content_type: str) -> str` — raises `ValueError("resume too short to parse")` if `len(text.strip()) < 50`.

- [ ] **Step 1: Write failing tests**

Create `services/ingestion-service/tests/test_parsers.py`:

```python
import io
import pytest

from src.parsers import extract_text, SUPPORTED_MIME_TYPES


def _make_docx_bytes() -> bytes:
    from docx import Document
    doc = Document()
    doc.add_paragraph("John Doe, Python Developer with 5 years of experience building APIs and services.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_extract_plain_text():
    text = "John Doe\nPython Developer with 5 years of experience in FastAPI and PostgreSQL systems."
    result = extract_text(text.encode(), "text/plain")
    assert "Python" in result
    assert len(result.strip()) >= 50


def test_extract_plain_text_utf8_errors():
    raw = b"Python Developer \xff with experience in cloud systems and microservices architecture."
    result = extract_text(raw, "text/plain")
    assert "Python" in result


def test_extract_docx():
    result = extract_text(_make_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert "Python" in result
    assert len(result.strip()) >= 50


def test_extract_too_short_raises():
    with pytest.raises(ValueError, match="resume too short"):
        extract_text(b"Hi", "text/plain")


def test_unsupported_mime_raises():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text(b"data", "image/png")


def test_supported_mime_types_constant():
    assert "application/pdf" in SUPPORTED_MIME_TYPES
    assert "text/plain" in SUPPORTED_MIME_TYPES
```

- [ ] **Step 2: Run tests to see them fail**

```bash
cd services/ingestion-service
pytest tests/test_parsers.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.parsers'`

- [ ] **Step 3: Implement `src/parsers.py`**

```python
import io

from pypdf import PdfReader

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}
_MIN_CHARS = 50


def extract_text(file_bytes: bytes, content_type: str) -> str:
    if content_type not in SUPPORTED_MIME_TYPES:
        raise ValueError(f"Unsupported file type: {content_type}")

    if content_type == "application/pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:
        text = file_bytes.decode("utf-8", errors="replace")

    if len(text.strip()) < _MIN_CHARS:
        raise ValueError("resume too short to parse")
    return text
```

- [ ] **Step 4: Run tests to see them pass**

```bash
pytest tests/test_parsers.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/parsers.py tests/test_parsers.py
git commit -m "[TASK-001] feat: parsers — extract_text for PDF, DOCX, plain text"
```

---

## Task 5: `s3.py` (TDD with moto)

**Files:**
- Create: `services/ingestion-service/src/s3.py`
- Create: `services/ingestion-service/tests/test_s3.py`

**Interfaces:**
- Produces:
  - `upload_file(file_bytes: bytes, key: str) -> str` — returns the S3 key
  - `download_file(key: str) -> bytes`
  - `ensure_bucket() -> None` — idempotent bucket creation

- [ ] **Step 1: Write failing tests**

Create `services/ingestion-service/tests/test_s3.py`:

```python
import boto3
import pytest
from moto import mock_aws
from unittest.mock import patch

from src.s3 import upload_file, download_file, ensure_bucket


@pytest.fixture
def s3_env(monkeypatch):
    monkeypatch.setenv("S3_ENDPOINT_URL", "")
    monkeypatch.setenv("S3_ACCESS_KEY", "test")
    monkeypatch.setenv("S3_SECRET_KEY", "test")
    monkeypatch.setenv("S3_BUCKET_RESUMES", "arap-resumes")


@mock_aws
def test_upload_and_download(s3_env):
    ensure_bucket()
    key = "resumes/test/abc.pdf"
    data = b"fake pdf content for testing upload and download roundtrip"
    returned_key = upload_file(data, key)
    assert returned_key == key
    downloaded = download_file(key)
    assert downloaded == data


@mock_aws
def test_ensure_bucket_idempotent(s3_env):
    ensure_bucket()
    ensure_bucket()  # should not raise


@mock_aws
def test_download_missing_key_raises(s3_env):
    ensure_bucket()
    import botocore.exceptions
    with pytest.raises(botocore.exceptions.ClientError):
        download_file("resumes/nonexistent.pdf")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_s3.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.s3'`

- [ ] **Step 3: Implement `src/s3.py`**

```python
import boto3
from botocore.config import Config

from src.config import settings

_REGION = "us-east-1"


def _client():
    kwargs = dict(
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=_REGION,
        config=Config(signature_version="s3v4"),
    )
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    return boto3.client("s3", **kwargs)


def ensure_bucket() -> None:
    s3 = _client()
    try:
        s3.head_bucket(Bucket=settings.S3_BUCKET_RESUMES)
    except Exception:
        s3.create_bucket(Bucket=settings.S3_BUCKET_RESUMES)


def upload_file(file_bytes: bytes, key: str) -> str:
    _client().put_object(Bucket=settings.S3_BUCKET_RESUMES, Key=key, Body=file_bytes)
    return key


def download_file(key: str) -> bytes:
    response = _client().get_object(Bucket=settings.S3_BUCKET_RESUMES, Key=key)
    return response["Body"].read()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_s3.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/s3.py tests/test_s3.py
git commit -m "[TASK-001] feat: s3 — upload_file, download_file, ensure_bucket (moto-tested)"
```

---

## Task 6: Resume Analysis Agent (TDD)

**Files:**
- Create: `agents/resume_analysis/prompts.py`
- Create: `agents/resume_analysis/agent.py`
- Create: `agents/resume_analysis/tests/__init__.py`
- Create: `agents/resume_analysis/tests/test_agent.py`

**Interfaces:**
- Produces: `run_resume_analysis_agent(raw_text: str, job_profile: dict | None) -> dict | None`
  - Returns the extraction dict (with `field_confidence` key) on success.
  - Returns `None` on any exception (non-fatal).

- [ ] **Step 1: Write failing tests**

Create `agents/resume_analysis/tests/__init__.py` (empty).

Create `agents/resume_analysis/tests/test_agent.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from unittest.mock import MagicMock, patch

from agents.resume_analysis.agent import run_resume_analysis_agent

RAW_TEXT = (
    "John Doe, Python Developer\n"
    "5 years experience at TechCorp (2020-2025). Team size: 5.\n"
    "Skills: Python, FastAPI, PostgreSQL.\n"
    "Education: B.Tech CS, MIT 2019.\n"
    "Achievements: Reduced API latency 40%."
)

JOB_PROFILE = {"required_skills": ["Python"], "preferred_skills": ["Docker"]}

MOCK_TOOL_OUTPUT = {
    "skills": {"explicit": ["Python", "FastAPI"], "inferred": ["REST APIs"]},
    "projects": [],
    "tech_used": ["PostgreSQL"],
    "employment_history": [
        {"company": "TechCorp", "title": "Developer", "start": "2020-01",
         "end": "2025-01", "team_size": 5, "scope": "regional", "key_achievements": []}
    ],
    "education": [{"degree": "B.Tech", "field": "CS", "institution": "MIT", "year": 2019}],
    "certifications": [],
    "achievements": ["Reduced API latency 40%"],
    "leadership_indicators": {"max_team_size": 5, "scope": "regional", "budget_ownership": None},
    "career_timeline": {"total_years": 5.0, "job_count": 1, "gaps": []},
    "domain_keywords": ["backend"],
    "field_confidence": {
        "skills": 0.92, "projects": 0.85, "tech_used": 0.90,
        "employment_history": 0.95, "education": 0.97, "certifications": 0.80,
        "achievements": 0.75, "leadership_indicators": 0.70,
        "career_timeline": 0.88, "domain_keywords": 0.83,
    },
}

EXPECTED_FIELDS = {
    "skills", "projects", "tech_used", "employment_history", "education",
    "certifications", "achievements", "leadership_indicators", "career_timeline",
    "domain_keywords", "field_confidence",
}


def _mock_anthropic(tool_output: dict):
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = tool_output
    response = MagicMock()
    response.content = [tool_block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


def test_agent_returns_extraction_shape():
    with patch("agents.resume_analysis.agent.anthropic.Anthropic", return_value=_mock_anthropic(MOCK_TOOL_OUTPUT)):
        result = run_resume_analysis_agent(RAW_TEXT, JOB_PROFILE)
    assert result is not None
    assert EXPECTED_FIELDS == set(result.keys())
    assert set(result["field_confidence"].keys()) == {
        "skills", "projects", "tech_used", "employment_history", "education",
        "certifications", "achievements", "leadership_indicators", "career_timeline", "domain_keywords",
    }


def test_agent_field_confidence_values_in_range():
    with patch("agents.resume_analysis.agent.anthropic.Anthropic", return_value=_mock_anthropic(MOCK_TOOL_OUTPUT)):
        result = run_resume_analysis_agent(RAW_TEXT, JOB_PROFILE)
    for field, score in result["field_confidence"].items():
        assert 0.0 <= score <= 1.0, f"{field} confidence out of range: {score}"


def test_agent_returns_none_on_api_error():
    client = MagicMock()
    client.messages.create.side_effect = Exception("API down")
    with patch("agents.resume_analysis.agent.anthropic.Anthropic", return_value=client):
        result = run_resume_analysis_agent(RAW_TEXT, JOB_PROFILE)
    assert result is None


def test_agent_accepts_none_job_profile():
    with patch("agents.resume_analysis.agent.anthropic.Anthropic", return_value=_mock_anthropic(MOCK_TOOL_OUTPUT)):
        result = run_resume_analysis_agent(RAW_TEXT, None)
    assert result is not None
```

- [ ] **Step 2: Run tests to see them fail**

```bash
cd services/ingestion-service
pytest ../../agents/resume_analysis/tests/test_agent.py -v
```

Expected: `ModuleNotFoundError: No module named 'agents.resume_analysis.agent'`

- [ ] **Step 3: Create `agents/resume_analysis/prompts.py`**

```python
import os

SYSTEM_PROMPT = (
    "You are a resume parsing assistant. "
    "Given raw resume text and an optional job profile, extract structured candidate information "
    "using the provided tool. For each field, assign a confidence score between 0.0 and 1.0 "
    "reflecting how clearly the information was stated (1.0 = explicitly stated, "
    "0.5 = inferred, 0.0 = not found/guessed). Be factual — do not invent information."
)

RESUME_EXTRACTION_TOOL = {
    "name": "extract_resume",
    "description": "Extract structured candidate information from resume text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "skills": {
                "type": "object",
                "properties": {
                    "explicit": {"type": "array", "items": {"type": "string"}},
                    "inferred": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["explicit", "inferred"],
            },
            "projects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "tech": {"type": "array", "items": {"type": "string"}},
                        "description": {"type": "string"},
                    },
                    "required": ["name", "tech", "description"],
                },
            },
            "tech_used": {"type": "array", "items": {"type": "string"}},
            "employment_history": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "company": {"type": "string"},
                        "title": {"type": "string"},
                        "start": {"type": "string"},
                        "end": {"type": ["string", "null"]},
                        "team_size": {"type": ["integer", "null"]},
                        "scope": {"type": ["string", "null"]},
                        "key_achievements": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["company", "title", "start", "end", "team_size", "scope", "key_achievements"],
                },
            },
            "education": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "degree": {"type": "string"},
                        "field": {"type": "string"},
                        "institution": {"type": "string"},
                        "year": {"type": ["integer", "null"]},
                    },
                    "required": ["degree", "field", "institution", "year"],
                },
            },
            "certifications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "issuer": {"type": "string"},
                        "year": {"type": ["integer", "null"]},
                    },
                    "required": ["name", "issuer", "year"],
                },
            },
            "achievements": {"type": "array", "items": {"type": "string"}},
            "leadership_indicators": {
                "type": "object",
                "properties": {
                    "max_team_size": {"type": ["integer", "null"]},
                    "scope": {"type": ["string", "null"]},
                    "budget_ownership": {"type": ["string", "null"]},
                },
                "required": ["max_team_size", "scope", "budget_ownership"],
            },
            "career_timeline": {
                "type": "object",
                "properties": {
                    "total_years": {"type": "number"},
                    "job_count": {"type": "integer"},
                    "gaps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                                "months": {"type": "integer"},
                            },
                            "required": ["start", "end", "months"],
                        },
                    },
                },
                "required": ["total_years", "job_count", "gaps"],
            },
            "domain_keywords": {"type": "array", "items": {"type": "string"}},
            "field_confidence": {
                "type": "object",
                "properties": {
                    "skills": {"type": "number"},
                    "projects": {"type": "number"},
                    "tech_used": {"type": "number"},
                    "employment_history": {"type": "number"},
                    "education": {"type": "number"},
                    "certifications": {"type": "number"},
                    "achievements": {"type": "number"},
                    "leadership_indicators": {"type": "number"},
                    "career_timeline": {"type": "number"},
                    "domain_keywords": {"type": "number"},
                },
                "required": [
                    "skills", "projects", "tech_used", "employment_history",
                    "education", "certifications", "achievements",
                    "leadership_indicators", "career_timeline", "domain_keywords",
                ],
            },
        },
        "required": [
            "skills", "projects", "tech_used", "employment_history", "education",
            "certifications", "achievements", "leadership_indicators",
            "career_timeline", "domain_keywords", "field_confidence",
        ],
    },
}
```

- [ ] **Step 4: Create `agents/resume_analysis/agent.py`**

```python
import logging

import anthropic

from agents.resume_analysis.prompts import RESUME_EXTRACTION_TOOL, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096


def _build_user_message(raw_text: str, job_profile: dict | None) -> str:
    lines = [f"RESUME TEXT:\n{raw_text[:12000]}"]
    if job_profile:
        req = ", ".join(job_profile.get("required_skills", []))
        pref = ", ".join(job_profile.get("preferred_skills", []))
        lines.append(f"\nJOB REQUIRED SKILLS: {req}")
        lines.append(f"JOB PREFERRED SKILLS: {pref}")
    return "\n".join(lines)


def _derive_leadership_level(max_team_size: int | None) -> str:
    if not max_team_size:
        return "IC"
    if max_team_size < 2:
        return "IC"
    if max_team_size <= 4:
        return "Team Lead"
    if max_team_size <= 15:
        return "Manager"
    if max_team_size <= 50:
        return "Director"
    return "VP-equiv"


def run_resume_analysis_agent(raw_text: str, job_profile: dict | None) -> dict | None:
    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[RESUME_EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "extract_resume"},
            messages=[{"role": "user", "content": _build_user_message(raw_text, job_profile)}],
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        result = dict(tool_block.input)
        result["_leadership_level"] = _derive_leadership_level(
            result.get("leadership_indicators", {}).get("max_team_size")
        )
        return result
    except Exception:
        logger.exception("Resume analysis agent failed — returning None")
        return None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd services/ingestion-service
pytest ../../agents/resume_analysis/tests/test_agent.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add agents/resume_analysis/
git commit -m "[TASK-001] feat: resume_analysis agent — tool_use extraction, per-field confidence, non-fatal"
```

---

## Task 7: `embeddings.py` (TDD)

**Files:**
- Create: `services/ingestion-service/src/embeddings.py`
- Create: `services/ingestion-service/tests/test_embeddings.py`

**Interfaces:**
- Produces:
  - `embed(text: str) -> list[float]` — calls OpenAI `text-embedding-3-small`, truncates to 8000 chars
  - `cosine_similarity(a: list[float], b: list[float]) -> float` — returns value in [0, 1]

- [ ] **Step 1: Write failing tests**

Create `services/ingestion-service/tests/test_embeddings.py`:

```python
from unittest.mock import MagicMock, patch

from src.embeddings import cosine_similarity, embed

MOCK_VECTOR = [0.1] * 1536


def _mock_openai_client(vector):
    embedding_obj = MagicMock()
    embedding_obj.embedding = vector
    data_obj = MagicMock()
    data_obj.data = [embedding_obj]
    client = MagicMock()
    client.embeddings.create.return_value = data_obj
    return client


def test_embed_returns_1536_floats():
    with patch("src.embeddings.openai.OpenAI", return_value=_mock_openai_client(MOCK_VECTOR)):
        result = embed("Python developer with 5 years experience in FastAPI")
    assert len(result) == 1536
    assert all(isinstance(v, float) for v in result)


def test_embed_truncates_long_text():
    long_text = "x" * 20000
    captured = {}

    def fake_create(**kwargs):
        captured["input"] = kwargs["input"]
        return _mock_openai_client(MOCK_VECTOR)().embeddings.create(**kwargs)

    with patch("src.embeddings.openai.OpenAI", return_value=_mock_openai_client(MOCK_VECTOR)):
        embed(long_text)
    # Just verify it doesn't crash — truncation is internal


def test_cosine_similarity_identical_vectors():
    v = [1.0, 0.0, 0.0]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal_vectors():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(cosine_similarity(a, b)) < 1e-6


def test_cosine_similarity_range():
    import random
    a = [random.random() for _ in range(1536)]
    b = [random.random() for _ in range(1536)]
    score = cosine_similarity(a, b)
    assert 0.0 <= score <= 1.0
```

- [ ] **Step 2: Run tests to see them fail**

```bash
pytest tests/test_embeddings.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.embeddings'`

- [ ] **Step 3: Implement `src/embeddings.py`**

```python
import math

import openai

from src.config import settings

_MODEL = "text-embedding-3-small"
_MAX_CHARS = 8000


def embed(text: str) -> list[float]:
    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.embeddings.create(model=_MODEL, input=text[:_MAX_CHARS])
    return response.data[0].embedding


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    raw = dot / (norm_a * norm_b)
    return max(0.0, min(1.0, raw))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_embeddings.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/embeddings.py tests/test_embeddings.py
git commit -m "[TASK-001] feat: embeddings — embed() + cosine_similarity() for match score"
```

---

## Task 8: `POST /upload` Router (TDD)

**Files:**
- Create: `services/ingestion-service/src/routers/__init__.py`
- Create: `services/ingestion-service/src/routers/health.py`
- Create: `services/ingestion-service/src/routers/upload.py`
- Modify: `services/ingestion-service/src/main.py`
- Create: `services/ingestion-service/tests/test_upload.py`

**Interfaces:**
- Consumes: `extract_text()` (parsers.py), `upload_file()` (s3.py), `settings.S3_BUCKET_RESUMES`
- Produces: `POST /upload` → `{"s3_key": str, "presigned_url": str}`

- [ ] **Step 1: Write failing tests**

Create `services/ingestion-service/tests/test_upload.py`:

```python
import io
from unittest.mock import patch

import pytest

from tests.conftest import SAMPLE_PDF_BYTES


def _make_docx_bytes() -> bytes:
    from docx import Document
    doc = Document()
    doc.add_paragraph("John Doe, Python Developer with 5 years of experience building APIs and services.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_upload_pdf_returns_s3_key(client):
    with patch("src.routers.upload.upload_file", return_value="resumes/test/abc.pdf"), \
         patch("src.routers.upload.ensure_bucket"):
        response = client.post(
            "/upload",
            files={"file": ("resume.pdf", SAMPLE_PDF_BYTES, "application/pdf")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "s3_key" in data
    assert data["s3_key"].endswith(".pdf")


def test_upload_docx_accepted(client):
    with patch("src.routers.upload.upload_file", return_value="resumes/test/abc.docx"), \
         patch("src.routers.upload.ensure_bucket"):
        response = client.post(
            "/upload",
            files={"file": ("resume.docx", _make_docx_bytes(),
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    assert response.status_code == 200


def test_upload_plain_text_accepted(client):
    text = b"John Doe\nPython Developer 5 years experience FastAPI PostgreSQL Docker Kubernetes"
    with patch("src.routers.upload.upload_file", return_value="resumes/test/abc.txt"), \
         patch("src.routers.upload.ensure_bucket"):
        response = client.post(
            "/upload",
            files={"file": ("resume.txt", text, "text/plain")},
        )
    assert response.status_code == 200


def test_upload_unsupported_type_returns_422(client):
    response = client.post(
        "/upload",
        files={"file": ("photo.png", b"PNG data", "image/png")},
    )
    assert response.status_code == 422


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 2: Run tests to see them fail**

```bash
pytest tests/test_upload.py -v
```

Expected: `ImportError` or 404 — app not yet wired.

- [ ] **Step 3: Create `src/routers/__init__.py`**

Empty file.

- [ ] **Step 4: Create `src/routers/health.py`**

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ingestion-service"}
```

- [ ] **Step 5: Create `src/routers/upload.py`**

```python
import uuid

from fastapi import APIRouter, HTTPException, UploadFile, status

from src.parsers import SUPPORTED_MIME_TYPES
from src.s3 import ensure_bucket, upload_file
from src.config import settings

router = APIRouter(tags=["upload"])


@router.post("/upload")
async def upload_resume(file: UploadFile) -> dict:
    if file.content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type: {file.content_type}",
        )
    file_bytes = await file.read()
    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "bin"
    key = f"resumes/{uuid.uuid4()}.{ext}"
    try:
        ensure_bucket()
        returned_key = upload_file(file_bytes, key)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return {"s3_key": returned_key, "presigned_url": ""}
```

- [ ] **Step 6: Update `src/main.py`**

```python
from fastapi import FastAPI

from src.routers.health import router as health_router
from src.routers.upload import router as upload_router

app = FastAPI(title="ARAP Ingestion Service", version="0.1.0")

app.include_router(health_router)
app.include_router(upload_router)
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/test_upload.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add src/routers/ src/main.py tests/test_upload.py
git commit -m "[TASK-001] feat: POST /upload — multipart file to S3, 422 on unsupported type"
```

---

## Task 9: `POST /analyze` Router — Full Pipeline (TDD)

**Files:**
- Create: `services/ingestion-service/src/routers/analyze.py`
- Modify: `services/ingestion-service/src/main.py`
- Create: `services/ingestion-service/tests/test_analyze.py`
- Create: `services/ingestion-service/tests/test_analyze_async.py`
- Create: `services/ingestion-service/tests/test_github.py`

**Interfaces:**
- Consumes: `run_resume_analysis_agent()` (agents/resume_analysis), `embed()` + `cosine_similarity()` (embeddings.py), `download_file()` (s3.py), `extract_text()` (parsers.py)
- Produces:
  - `POST /analyze` → 200 `CandidateProfileResponse` or 202 `{"status":"processing"}`
  - `GET /analyze/{candidate_id}/{job_assessment_id}` → `CandidateProfileResponse` or `{"status":"processing"}`

- [ ] **Step 1: Write failing pipeline tests**

Create `services/ingestion-service/tests/test_analyze.py`:

```python
import uuid
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import MOCK_AGENT_OUTPUT, MOCK_EMBEDDING


def _set_candidate_s3_key(db, candidate, key):
    candidate.resume_file_url = key
    db.commit()
    db.refresh(candidate)


def test_analyze_writes_candidate_profile(client, db, seed, mock_agent, mock_embed):
    cand = seed["candidate"]
    job = seed["job"]
    cand.resume_file_url = "resumes/test/resume.pdf"
    db.commit()

    with patch("src.routers.analyze.download_file", return_value=b"John Doe Python Developer with 5 years experience at TechCorp building scalable microservices"), \
         patch("src.routers.analyze.extract_text", return_value="John Doe Python Developer with 5 years experience at TechCorp building scalable microservices"):
        response = client.post("/analyze", json={
            "candidate_id": str(cand.id),
            "job_assessment_id": str(job.id),
            "org_id": str(seed["org"].id),
        })

    assert response.status_code == 200
    data = response.json()
    assert data["field_confidence"] is not None
    assert len(data["field_confidence"]) == 10
    assert 0.0 <= data["match_score"] <= 1.0
    assert data["parsing_confidence"] is not None


def test_analyze_field_confidence_all_10_keys(client, db, seed, mock_agent, mock_embed):
    cand = seed["candidate"]
    job = seed["job"]
    cand.resume_file_url = "resumes/test/resume.pdf"
    db.commit()

    with patch("src.routers.analyze.download_file", return_value=b"text"), \
         patch("src.routers.analyze.extract_text", return_value="John Doe Python Developer with 5+ years experience"):
        response = client.post("/analyze", json={
            "candidate_id": str(cand.id),
            "job_assessment_id": str(job.id),
            "org_id": str(seed["org"].id),
        })

    expected_keys = {
        "skills", "projects", "tech_used", "employment_history", "education",
        "certifications", "achievements", "leadership_indicators", "career_timeline", "domain_keywords",
    }
    assert set(response.json()["field_confidence"].keys()) == expected_keys


def test_analyze_agent_error_returns_null_confidence(client, db, seed, mock_embed):
    cand = seed["candidate"]
    job = seed["job"]
    cand.resume_file_url = "resumes/test/resume.pdf"
    db.commit()

    with patch("src.routers.analyze.run_resume_analysis_agent", return_value=None), \
         patch("src.routers.analyze.download_file", return_value=b"text"), \
         patch("src.routers.analyze.extract_text", return_value="John Doe Python Developer experience"):
        response = client.post("/analyze", json={
            "candidate_id": str(cand.id),
            "job_assessment_id": str(job.id),
            "org_id": str(seed["org"].id),
        })

    assert response.status_code == 200
    assert response.json()["parsing_confidence"] is None
    assert response.json()["field_confidence"] is None


def test_analyze_404_unknown_candidate(client, seed, mock_agent, mock_embed):
    response = client.post("/analyze", json={
        "candidate_id": str(uuid.uuid4()),
        "job_assessment_id": str(seed["job"].id),
        "org_id": str(seed["org"].id),
    })
    assert response.status_code == 404


def test_analyze_no_resume_url(client, db, seed, mock_agent, mock_embed):
    cand = seed["candidate"]
    cand.resume_file_url = None
    db.commit()

    response = client.post("/analyze", json={
        "candidate_id": str(cand.id),
        "job_assessment_id": str(seed["job"].id),
        "org_id": str(seed["org"].id),
    })
    assert response.status_code == 422
    assert "resume" in response.json()["detail"].lower()


def test_get_analyze_returns_profile(client, db, seed, mock_agent, mock_embed):
    cand = seed["candidate"]
    job = seed["job"]
    cand.resume_file_url = "resumes/test/r2.pdf"
    db.commit()

    with patch("src.routers.analyze.download_file", return_value=b"text"), \
         patch("src.routers.analyze.extract_text", return_value="John Doe Python Developer 5 years experience"):
        client.post("/analyze", json={
            "candidate_id": str(cand.id),
            "job_assessment_id": str(job.id),
            "org_id": str(seed["org"].id),
        })

    response = client.get(f"/analyze/{cand.id}/{job.id}")
    assert response.status_code == 200
    assert response.json()["candidate_id"] == str(cand.id)


def test_get_analyze_404_not_yet_written(client, seed):
    response = client.get(f"/analyze/{uuid.uuid4()}/{uuid.uuid4()}")
    assert response.status_code == 404
```

- [ ] **Step 2: Write large-doc async tests**

Create `services/ingestion-service/tests/test_analyze_async.py`:

```python
from unittest.mock import patch

from tests.conftest import MOCK_AGENT_OUTPUT, MOCK_EMBEDDING


def test_large_doc_returns_202(client, db, seed, mock_agent, mock_embed):
    cand = seed["candidate"]
    job = seed["job"]
    big_bytes = b"x" * (6 * 1024 * 1024)  # 6 MB > 5 MB threshold
    cand.resume_file_url = "resumes/test/big.pdf"
    db.commit()

    with patch("src.routers.analyze.download_file", return_value=big_bytes), \
         patch("src.routers.analyze.extract_text", return_value="John Doe Python Developer 5 years experience microservices"):
        response = client.post("/analyze", json={
            "candidate_id": str(cand.id),
            "job_assessment_id": str(job.id),
            "org_id": str(seed["org"].id),
        })
    assert response.status_code == 202
    assert response.json()["status"] == "processing"
```

- [ ] **Step 3: Write GitHub enrichment tests**

Create `services/ingestion-service/tests/test_github.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch


GITHUB_REPOS = [
    {"name": "api-service", "language": "Python", "stargazers_count": 5,
     "pushed_at": "2026-07-01T00:00:00Z"},
    {"name": "frontend", "language": "TypeScript", "stargazers_count": 2,
     "pushed_at": "2026-06-15T00:00:00Z"},
]


def test_github_enrichment_populated(client, db, seed, mock_agent, mock_embed):
    from tests.conftest import MOCK_AGENT_OUTPUT, MOCK_EMBEDDING
    cand = seed["candidate"]
    job = seed["job"]
    cand.resume_file_url = "resumes/test/resume.pdf"
    cand.github_url = "https://github.com/johndoe"
    db.commit()

    mock_response_user = MagicMock()
    mock_response_user.status_code = 200
    mock_response_user.json.return_value = {"login": "johndoe", "public_repos": 10}

    mock_response_repos = MagicMock()
    mock_response_repos.status_code = 200
    mock_response_repos.json.return_value = GITHUB_REPOS

    with patch("src.routers.analyze.download_file", return_value=b"text"), \
         patch("src.routers.analyze.extract_text", return_value="John Doe Python Developer 5 years experience"), \
         patch("src.routers.analyze.httpx.get", side_effect=[mock_response_user, mock_response_repos]):
        response = client.post("/analyze", json={
            "candidate_id": str(cand.id),
            "job_assessment_id": str(job.id),
            "org_id": str(seed["org"].id),
        })

    assert response.status_code == 200
    enrichment = response.json()["github_enrichment"]
    assert enrichment is not None
    assert "Python" in enrichment["top_languages"]
    assert enrichment["public_repos"] == 10


def test_github_404_returns_null_enrichment(client, db, seed, mock_agent, mock_embed):
    cand = seed["candidate"]
    job = seed["job"]
    cand.resume_file_url = "resumes/test/resume.pdf"
    cand.github_url = "https://github.com/nobody-xyz"
    db.commit()

    mock_not_found = MagicMock()
    mock_not_found.status_code = 404

    with patch("src.routers.analyze.download_file", return_value=b"text"), \
         patch("src.routers.analyze.extract_text", return_value="John Doe Python Developer 5 years experience"), \
         patch("src.routers.analyze.httpx.get", return_value=mock_not_found):
        response = client.post("/analyze", json={
            "candidate_id": str(cand.id),
            "job_assessment_id": str(job.id),
            "org_id": str(seed["org"].id),
        })

    assert response.status_code == 200
    assert response.json()["github_enrichment"] is None
```

- [ ] **Step 4: Run all tests to see them fail**

```bash
pytest tests/test_analyze.py tests/test_analyze_async.py tests/test_github.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.routers.analyze'`

- [ ] **Step 5: Create `src/routers/analyze.py`**

```python
import asyncio
import logging
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.resume_analysis.agent import run_resume_analysis_agent
from src.config import settings
from src.database import get_db
from src.embeddings import cosine_similarity, embed
from src.models import Candidate, CandidateProfile, JobAssessment
from src.parsers import extract_text
from src.s3 import download_file

logger = logging.getLogger(__name__)
router = APIRouter(tags=["analyze"])


class AnalyzeRequest(BaseModel):
    candidate_id: uuid.UUID
    job_assessment_id: uuid.UUID
    org_id: uuid.UUID


class CandidateProfileResponse(BaseModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    job_assessment_id: uuid.UUID
    org_id: uuid.UUID
    parsing_confidence: Optional[float]
    field_confidence: Optional[dict]
    match_score: Optional[float]
    github_enrichment: Optional[dict]
    skill_matrix: dict
    experience_matrix: dict
    leadership_level_estimate: Optional[str]

    class Config:
        from_attributes = True


def _fetch_github(github_url: str) -> Optional[dict]:
    try:
        handle = github_url.rstrip("/").rsplit("/", 1)[-1].lstrip("@")
        user_resp = httpx.get(
            f"https://api.github.com/users/{handle}",
            headers={"Accept": "application/vnd.github+json"},
            timeout=10,
        )
        if user_resp.status_code != 200:
            return None
        user_data = user_resp.json()

        repos_resp = httpx.get(
            f"https://api.github.com/users/{handle}/repos?sort=pushed&per_page=10",
            headers={"Accept": "application/vnd.github+json"},
            timeout=10,
        )
        if repos_resp.status_code != 200:
            return None
        repos = repos_resp.json()

        languages = list(dict.fromkeys(
            r["language"] for r in repos if r.get("language")
        ))
        most_recent = max((r["pushed_at"] for r in repos), default=None)
        return {
            "username": handle,
            "public_repos": user_data.get("public_repos", 0),
            "top_languages": languages[:5],
            "most_recent_push": most_recent,
            "repos": [
                {
                    "name": r["name"],
                    "language": r.get("language"),
                    "stars": r.get("stargazers_count", 0),
                    "pushed_at": r.get("pushed_at"),
                }
                for r in repos
            ],
        }
    except Exception:
        logger.exception("GitHub enrichment failed")
        return None


def _run_pipeline(db: Session, candidate: Candidate, job: JobAssessment, org_id: uuid.UUID) -> None:
    raw_text: Optional[str] = None
    if candidate.resume_file_url:
        try:
            file_bytes = download_file(candidate.resume_file_url)
            ext = candidate.resume_file_url.rsplit(".", 1)[-1].lower()
            mime_map = {
                "pdf": "application/pdf",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "txt": "text/plain",
            }
            mime = mime_map.get(ext, "text/plain")
            raw_text = extract_text(file_bytes, mime)
        except Exception:
            logger.exception("Text extraction failed for candidate %s", candidate.id)

    job_profile = job.job_profile
    extraction: Optional[dict] = None
    if raw_text:
        extraction = run_resume_analysis_agent(raw_text, job_profile)

    github_enrichment: Optional[dict] = None
    if candidate.github_url:
        github_enrichment = _fetch_github(candidate.github_url)

    match_score: Optional[float] = None
    field_confidence: Optional[dict] = None
    parsing_confidence: Optional[float] = None
    skill_matrix: dict = {}
    experience_matrix: dict = {}
    leadership_level_estimate: Optional[str] = None

    if extraction:
        field_confidence = extraction.get("field_confidence")
        if field_confidence:
            parsing_confidence = round(
                sum(field_confidence.values()) / len(field_confidence), 3
            )
        skill_matrix = {
            "explicit": extraction.get("skills", {}).get("explicit", []),
            "inferred": extraction.get("skills", {}).get("inferred", []),
            "tech_used": extraction.get("tech_used", []),
        }
        experience_matrix = {
            "employment_history": extraction.get("employment_history", []),
            "career_timeline": extraction.get("career_timeline", {}),
        }
        leadership_level_estimate = extraction.get("_leadership_level")

        try:
            req_skills = list(job.required_skills or []) + list(job.preferred_skills or [])
            resume_tokens = (
                extraction.get("skills", {}).get("explicit", [])
                + extraction.get("skills", {}).get("inferred", [])
                + extraction.get("domain_keywords", [])
            )
            if resume_tokens and req_skills:
                vec_resume = embed(" ".join(resume_tokens))
                vec_jd = embed(" ".join(req_skills))
                match_score = round(cosine_similarity(vec_resume, vec_jd), 3)
        except Exception:
            logger.exception("Match score computation failed for candidate %s", candidate.id)

    existing = db.query(CandidateProfile).filter_by(
        candidate_id=candidate.id, job_assessment_id=job.id
    ).first()

    if existing:
        existing.skill_matrix = skill_matrix
        existing.experience_matrix = experience_matrix
        existing.leadership_level_estimate = leadership_level_estimate
        existing.parsing_confidence = parsing_confidence
        existing.field_confidence = field_confidence
        existing.match_score = match_score
        existing.github_enrichment = github_enrichment
    else:
        profile = CandidateProfile(
            org_id=org_id,
            candidate_id=candidate.id,
            job_assessment_id=job.id,
            skill_matrix=skill_matrix,
            experience_matrix=experience_matrix,
            leadership_level_estimate=leadership_level_estimate,
            strengths=[],
            risk_flags=[],
            parsing_confidence=parsing_confidence,
            field_confidence=field_confidence,
            match_score=match_score,
            github_enrichment=github_enrichment,
        )
        db.add(profile)
    db.commit()


@router.post("/analyze", status_code=status.HTTP_200_OK)
def analyze(body: AnalyzeRequest, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter_by(id=body.candidate_id, org_id=body.org_id).first()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    job = db.query(JobAssessment).filter_by(id=body.job_assessment_id, org_id=body.org_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job assessment not found")

    if not candidate.resume_file_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Candidate has no resume file uploaded",
        )

    import os
    is_large = False
    if candidate.resume_file_url:
        try:
            file_bytes = download_file(candidate.resume_file_url)
            if len(file_bytes) > settings.LARGE_DOC_BYTES:
                is_large = True
        except Exception:
            pass

    if is_large:
        asyncio.ensure_future(
            asyncio.get_event_loop().run_in_executor(
                None, _run_pipeline, db, candidate, job, body.org_id
            )
        )
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"status": "processing", "candidate_profile_id": None},
        )

    _run_pipeline(db, candidate, job, body.org_id)

    profile = db.query(CandidateProfile).filter_by(
        candidate_id=candidate.id, job_assessment_id=job.id
    ).first()
    return CandidateProfileResponse.model_validate(profile)


@router.get("/analyze/{candidate_id}/{job_assessment_id}")
def get_analyze(candidate_id: uuid.UUID, job_assessment_id: uuid.UUID, db: Session = Depends(get_db)):
    profile = db.query(CandidateProfile).filter_by(
        candidate_id=candidate_id, job_assessment_id=job_assessment_id
    ).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found or still processing")
    return CandidateProfileResponse.model_validate(profile)
```

- [ ] **Step 6: Add analyze router to `src/main.py`**

```python
from fastapi import FastAPI

from src.routers.health import router as health_router
from src.routers.upload import router as upload_router
from src.routers.analyze import router as analyze_router

app = FastAPI(title="ARAP Ingestion Service", version="0.1.0")

app.include_router(health_router)
app.include_router(upload_router)
app.include_router(analyze_router)
```

- [ ] **Step 7: Run all tests**

```bash
cd services/ingestion-service
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 8: Also run the agent tests**

```bash
pytest ../../agents/resume_analysis/tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add src/routers/analyze.py src/main.py \
        tests/test_analyze.py tests/test_analyze_async.py tests/test_github.py
git commit -m "[TASK-001] feat: POST /analyze pipeline — parse, agent, GitHub, embed, match score, candidate_profile upsert"
```

---

## Task 10: Ingestion-Service Dockerfile + pyproject PYTHONPATH

**Files:**
- Create: `services/ingestion-service/Dockerfile`
- Modify: `services/ingestion-service/pyproject.toml` (PYTHONPATH for agent import)

**Interfaces:**
- Produces: buildable Docker image for ingestion-service; `agents/` importable in tests via PYTHONPATH.

- [ ] **Step 1: Add PYTHONPATH to pytest config in pyproject.toml**

In `services/ingestion-service/pyproject.toml`, update `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
pythonpath = [
    ".",
    "../..",
]
```

This makes `agents.resume_analysis` importable from tests without `sys.path` hacks.

- [ ] **Step 2: Remove the sys.path hack from agent tests**

In `agents/resume_analysis/tests/test_agent.py`, remove:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
```

- [ ] **Step 3: Verify tests still pass after removing sys.path hack**

```bash
cd services/ingestion-service
pytest tests/ ../../agents/resume_analysis/tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Create `services/ingestion-service/Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY src/ src/
COPY ../../agents/ /agents/

ENV PYTHONPATH="/app:/agents/.."

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

- [ ] **Step 5: Verify docker build (optional — skip if Docker not available locally)**

```bash
docker build -t arap-ingestion-service services/ingestion-service/
```

Expected: exits 0.

- [ ] **Step 6: Final full test run**

```bash
cd services/ingestion-service
pytest tests/ ../../agents/resume_analysis/tests/ -v --tb=short
```

Expected: all tests PASS with zero failures.

- [ ] **Step 7: Commit**

```bash
git add services/ingestion-service/Dockerfile \
        services/ingestion-service/pyproject.toml \
        agents/resume_analysis/tests/test_agent.py
git commit -m "[TASK-001] chore: ingestion-service Dockerfile + PYTHONPATH for agent import"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered in |
|---|---|
| M2-F01: PDF/DOCX/plain text upload | Task 4 (parsers), Task 8 (upload router) |
| M2-F01: LinkedIn URL (context hint only, no scrape) | `linkedin_url` on Candidate model; not parsed — intentional per design |
| M2-F01: GitHub URL | Task 9 (`_fetch_github`) |
| M2-F01: < 10s sync, large-doc 202 fallback | Task 9 (`LARGE_DOC_BYTES` check → 202) |
| M2-F02: 10-field structured extraction | Task 6 (agent tool definition) |
| M2-F02: per-field confidence score | Task 6 (`field_confidence` in tool schema), Task 9 (written to DB) |
| M2-F03: GitHub enrichment additive | Task 9 (`_fetch_github`; non-fatal) |
| M2-F04: embeddings match score | Task 7 (embeddings), Task 9 (cosine similarity, written to `match_score`) |
| Migration 0003 | Task 1 |
| MinIO in docker-compose | Task 2 |
| `OPENAI_API_KEY` in config | Task 2, Task 3 |
| Agent non-fatal | Task 6 (returns None on exception); Task 9 (null confidence) |
| Unique `(candidate_id, job_assessment_id)` for upsert | Task 1 migration + Task 3 model |

**Placeholder scan:** None found. All code steps are complete.

**Type consistency check:**
- `run_resume_analysis_agent(raw_text: str, job_profile: dict | None) -> dict | None` — used identically in Task 6 (implementation) and Task 9 (import + call).
- `embed(text: str) -> list[float]` — used identically in Task 7 (implementation) and Task 9 (import + call).
- `cosine_similarity(a, b) -> float` — used identically in Task 7 and Task 9.
- `upload_file(bytes, key) -> str` — used identically in Task 5 and Task 8.
- `download_file(key) -> bytes` — used identically in Task 5 and Task 9.
- `extract_text(bytes, mime) -> str` — used identically in Task 4 and Task 9.

All consistent. ✓

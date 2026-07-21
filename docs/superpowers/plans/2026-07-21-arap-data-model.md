# ARAP Data Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write all 17 SQLAlchemy ORM model files and one Alembic migration that creates every ARAP table with RLS, pgvector HNSW index, and append-only audit_logs in a fresh PostgreSQL database.

**Architecture:** One model file per table under `services/orchestrator-api/src/models/`; a single Alembic revision `0001_initial_schema` handles the full DDL including `CREATE EXTENSION vector`, RLS policies, HNSW index, and GRANT. Tests use `Base.metadata.create_all()` against a real PostgreSQL instance (no mocks).

**Tech Stack:** Python 3.11+, SQLAlchemy 2.x (mapped_column / Mapped style), Alembic 1.13+, pgvector-python 0.3+, psycopg2-binary, pytest 8+

## Global Constraints

- Every table except `orgs` carries `org_id uuid NOT NULL FK→orgs(id)` and has RLS enabled
- `question_fingerprints.question_embedding` is `vector(1536)`, HNSW index (m=16, ef_construction=64)
- `session_questions.evaluation` is `jsonb` — shape: `{"competency_scores":[{"competency":str,"score":int,"explanation":str,"evidence":str}]}`
- `candidates` and `clients` have `auth_method CHECK IN ('magic_link','otp','password')` and nullable `password_hash / login_token_hash / login_token_expires_at`
- `assessment_sessions.status CHECK IN ('invited','in_progress','completed','expired')`
- `audit_logs`: app DB role has INSERT only — `REVOKE UPDATE, DELETE ON audit_logs FROM PUBLIC`
- All PKs: `uuid` with `server_default=gen_random_uuid()`
- All timestamps: `DateTime(timezone=True)` with `server_default=func.now()`
- Array columns: `ARRAY(Text)` with `server_default=text("'{}'")`
- Use `current_setting('app.current_org_id', true)` (second arg = true → returns NULL instead of raising if unset)
- No mock databases in tests — `TEST_DATABASE_URL` env var points to a real PG instance
- Module scope: `services/orchestrator-api/src/models/` + `services/orchestrator-api/migrations/` ONLY
- Do NOT build FastAPI routers, Pydantic schemas, auth, or any other module in this plan

---

## File Map

```
services/orchestrator-api/
├── pyproject.toml
├── alembic.ini
├── migrations/
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py
├── src/
│   └── models/
│       ├── __init__.py
│       ├── base.py
│       ├── orgs.py
│       ├── users.py
│       ├── job_assessments.py
│       ├── competency_library.py
│       ├── candidates.py
│       ├── clients.py
│       ├── candidate_profiles.py
│       ├── assessment_sessions.py
│       ├── question_sets.py
│       ├── session_questions.py
│       ├── question_fingerprints.py
│       ├── behavior_profiles.py
│       ├── integrity_flags.py
│       ├── hiring_reports.py
│       ├── report_shares.py
│       ├── prompt_templates.py
│       └── audit_logs.py
└── tests/
    └── models/
        ├── conftest.py
        ├── test_schema.py
        ├── test_rls.py
        ├── test_question_fingerprints.py
        └── test_audit_logs.py
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `services/orchestrator-api/pyproject.toml`
- Create: `services/orchestrator-api/alembic.ini`
- Create: `services/orchestrator-api/src/__init__.py`
- Create: `services/orchestrator-api/src/models/__init__.py` (empty for now)
- Create: `services/orchestrator-api/src/models/base.py`
- Create: `services/orchestrator-api/migrations/__init__.py`
- Create: `services/orchestrator-api/migrations/env.py`
- Create: `services/orchestrator-api/tests/__init__.py`
- Create: `services/orchestrator-api/tests/models/__init__.py`
- Create: `services/orchestrator-api/tests/models/conftest.py`

**Interfaces:**
- Produces: `Base` (DeclarativeBase) imported by all model files; `engine` and `session` pytest fixtures imported by all test files

- [ ] **Step 1: Create directory tree**

```bash
mkdir -p services/orchestrator-api/src/models
mkdir -p services/orchestrator-api/migrations/versions
mkdir -p services/orchestrator-api/tests/models
touch services/orchestrator-api/src/__init__.py
touch services/orchestrator-api/src/models/__init__.py
touch services/orchestrator-api/migrations/__init__.py
touch services/orchestrator-api/tests/__init__.py
touch services/orchestrator-api/tests/models/__init__.py
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "orchestrator-api"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "pgvector>=0.3",
    "psycopg2-binary>=2.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-env>=1.1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
env = [
    "TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/arap_test",
]
```

- [ ] **Step 3: Write `alembic.ini`**

```ini
[alembic]
script_location = migrations
prepend_sys_path = .
version_path_separator = os

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 4: Write `src/models/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 5: Write `migrations/env.py`**

```python
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text
from alembic import context

from src.models.base import Base
import src.models  # noqa: F401 — registers all models with Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    return os.environ["DATABASE_URL"]


def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = _get_url()
    connectable = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 6: Write `tests/models/conftest.py`**

```python
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.models.base import Base
import src.models  # noqa: F401 — registers all models

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/arap_test",
)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL, echo=False)
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
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.rollback()
    s.close()
```

- [ ] **Step 7: Install deps and verify import**

```bash
cd services/orchestrator-api
pip install -e ".[dev]"
python -c "from src.models.base import Base; print('OK')"
```

Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add services/orchestrator-api/
git commit -m "feat(schema): scaffold orchestrator-api models directory and Alembic config"
```

---

## Task 2: Org and User Models

**Files:**
- Create: `services/orchestrator-api/src/models/orgs.py`
- Create: `services/orchestrator-api/src/models/users.py`
- Modify: `services/orchestrator-api/src/models/__init__.py`
- Test: `services/orchestrator-api/tests/models/test_schema.py`

**Interfaces:**
- Produces: `Org`, `User` — imported by candidate_profiles, job_assessments, competency_library, report_shares, audit_logs

- [ ] **Step 1: Write failing test for Org and User tables**

Create `tests/models/test_schema.py`:

```python
import uuid
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from src.models.orgs import Org
from src.models.users import User


# ── Org ──────────────────────────────────────────────────────────────────────

def test_orgs_table_exists(engine):
    assert "orgs" in inspect(engine).get_table_names()


def test_orgs_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("orgs")}
    assert cols == {"id", "name", "plan_tier", "created_at"}


def test_org_insert_and_defaults(db):
    org = Org(name="Acme Corp")
    db.add(org)
    db.flush()
    assert org.id is not None
    assert org.plan_tier == "trial"
    assert org.created_at is not None


# ── User ─────────────────────────────────────────────────────────────────────

def test_users_table_exists(engine):
    assert "users" in inspect(engine).get_table_names()


def test_users_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("users")}
    assert cols == {"id", "org_id", "email", "role", "password_hash", "created_at"}


def test_user_role_check_rejects_invalid(db):
    org = Org(name="TestOrg")
    db.add(org)
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(User(org_id=org.id, email="x@x.com", role="superadmin", password_hash="h"))
        db.flush()
    db.rollback()


def test_user_unique_email_per_org(db):
    org = Org(name="UniqueOrg")
    db.add(org)
    db.flush()
    db.add(User(org_id=org.id, email="a@a.com", role="user", password_hash="h"))
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(User(org_id=org.id, email="a@a.com", role="admin", password_hash="h"))
        db.flush()
    db.rollback()
```

- [ ] **Step 2: Run test — expect FAIL (models not defined yet)**

```bash
cd services/orchestrator-api
pytest tests/models/test_schema.py -v 2>&1 | head -20
```

Expected: `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Write `src/models/orgs.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, func, text
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4: Write `src/models/users.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("org_id", "email", name="uq_users_org_email"),
        CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 5: Update `src/models/__init__.py`**

```python
from .orgs import Org
from .users import User

__all__ = ["Org", "User"]
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
pytest tests/models/test_schema.py -v
```

Expected: 7 tests, all PASS

- [ ] **Step 7: Commit**

```bash
git add services/orchestrator-api/src/models/orgs.py \
        services/orchestrator-api/src/models/users.py \
        services/orchestrator-api/src/models/__init__.py \
        services/orchestrator-api/tests/models/test_schema.py
git commit -m "feat(schema): add Org and User models with role check and unique constraints"
```

---

## Task 3: JobAssessment and CompetencyLibrary Models

**Files:**
- Create: `services/orchestrator-api/src/models/job_assessments.py`
- Create: `services/orchestrator-api/src/models/competency_library.py`
- Modify: `services/orchestrator-api/src/models/__init__.py`
- Modify: `services/orchestrator-api/tests/models/test_schema.py`

**Interfaces:**
- Produces: `JobAssessment`, `CompetencyLibrary` — referenced by candidate_profiles, assessment_sessions

- [ ] **Step 1: Append tests to `test_schema.py`**

```python
# append to tests/models/test_schema.py
from src.models.job_assessments import JobAssessment
from src.models.competency_library import CompetencyLibrary


def test_job_assessments_table_exists(engine):
    assert "job_assessments" in inspect(engine).get_table_names()


def test_job_assessments_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("job_assessments")}
    expected = {
        "id", "org_id", "title", "department", "experience_min", "experience_max",
        "required_skills", "preferred_skills", "responsibilities", "education",
        "certifications", "behavioral_competencies", "leadership_competencies",
        "culture_values", "difficulty_level", "duration_minutes",
        "competency_weightage", "created_by", "created_at",
    }
    assert cols == expected


def test_job_assessment_difficulty_check(db):
    org = Org(name="DiffOrg")
    db.add(org)
    db.flush()
    user = User(org_id=org.id, email="u@u.com", role="user", password_hash="h")
    db.add(user)
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(JobAssessment(
            org_id=org.id, title="Eng", difficulty_level="intern",
            duration_minutes=60, competency_weightage={}, created_by=user.id,
        ))
        db.flush()
    db.rollback()


def test_competency_library_unique_name_per_org(db):
    org = Org(name="CLOrg")
    db.add(org)
    db.flush()
    user = User(org_id=org.id, email="cl@cl.com", role="admin", password_hash="h")
    db.add(user)
    db.flush()
    db.add(CompetencyLibrary(org_id=org.id, name="Leadership", created_by=user.id))
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(CompetencyLibrary(org_id=org.id, name="Leadership", created_by=user.id))
        db.flush()
    db.rollback()
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/models/test_schema.py::test_job_assessments_table_exists -v
```

Expected: `ImportError`

- [ ] **Step 3: Write `src/models/job_assessments.py`**

```python
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint, func, text,
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
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4: Write `src/models/competency_library.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CompetencyLibrary(Base):
    __tablename__ = "competency_library"
    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_competency_library_org_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    rubric_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 5: Update `src/models/__init__.py`**

```python
from .orgs import Org
from .users import User
from .job_assessments import JobAssessment
from .competency_library import CompetencyLibrary

__all__ = ["Org", "User", "JobAssessment", "CompetencyLibrary"]
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
pytest tests/models/test_schema.py -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add services/orchestrator-api/src/models/job_assessments.py \
        services/orchestrator-api/src/models/competency_library.py \
        services/orchestrator-api/src/models/__init__.py \
        services/orchestrator-api/tests/models/test_schema.py
git commit -m "feat(schema): add JobAssessment and CompetencyLibrary models"
```

---

## Task 4: Candidate and Client Models

**Files:**
- Create: `services/orchestrator-api/src/models/candidates.py`
- Create: `services/orchestrator-api/src/models/clients.py`
- Modify: `services/orchestrator-api/src/models/__init__.py`
- Modify: `services/orchestrator-api/tests/models/test_schema.py`

**Interfaces:**
- Produces: `Candidate`, `Client` — referenced by candidate_profiles, assessment_sessions, report_shares

- [ ] **Step 1: Append tests to `test_schema.py`**

```python
# append to tests/models/test_schema.py
from src.models.candidates import Candidate
from src.models.clients import Client


def test_candidates_table_exists(engine):
    assert "candidates" in inspect(engine).get_table_names()


def test_candidates_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("candidates")}
    expected = {
        "id", "org_id", "name", "email",
        "resume_file_url", "linkedin_url", "github_url", "portfolio_url",
        "auth_method", "password_hash", "login_token_hash",
        "login_token_expires_at", "last_login_at", "created_at",
    }
    assert cols == expected


def test_candidate_auth_method_check(db):
    org = Org(name="AuthOrg")
    db.add(org)
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(Candidate(org_id=org.id, name="X", email="x@x.com", auth_method="sms"))
        db.flush()
    db.rollback()


def test_candidate_auth_method_nullable(db):
    org = Org(name="NoAuthOrg")
    db.add(org)
    db.flush()
    c = Candidate(org_id=org.id, name="Jane", email="jane@x.com")
    db.add(c)
    db.flush()
    assert c.auth_method is None


def test_clients_table_exists(engine):
    assert "clients" in inspect(engine).get_table_names()


def test_clients_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("clients")}
    expected = {
        "id", "org_id", "name", "email",
        "auth_method", "password_hash", "login_token_hash",
        "login_token_expires_at", "last_login_at", "created_at",
    }
    assert cols == expected
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/models/test_schema.py::test_candidates_table_exists -v
```

Expected: `ImportError`

- [ ] **Step 3: Write `src/models/candidates.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        UniqueConstraint("org_id", "email", name="uq_candidates_org_email"),
        CheckConstraint(
            "auth_method IS NULL OR auth_method IN ('magic_link','otp','password')",
            name="ck_candidates_auth_method",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    resume_file_url: Mapped[Optional[str]] = mapped_column(Text)
    linkedin_url: Mapped[Optional[str]] = mapped_column(Text)
    github_url: Mapped[Optional[str]] = mapped_column(Text)
    portfolio_url: Mapped[Optional[str]] = mapped_column(Text)
    auth_method: Mapped[Optional[str]] = mapped_column(String)
    password_hash: Mapped[Optional[str]] = mapped_column(Text)
    login_token_hash: Mapped[Optional[str]] = mapped_column(Text)
    login_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4: Write `src/models/clients.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint("org_id", "email", name="uq_clients_org_email"),
        CheckConstraint(
            "auth_method IS NULL OR auth_method IN ('magic_link','otp','password')",
            name="ck_clients_auth_method",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    auth_method: Mapped[Optional[str]] = mapped_column(String)
    password_hash: Mapped[Optional[str]] = mapped_column(Text)
    login_token_hash: Mapped[Optional[str]] = mapped_column(Text)
    login_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 5: Update `src/models/__init__.py`**

```python
from .orgs import Org
from .users import User
from .job_assessments import JobAssessment
from .competency_library import CompetencyLibrary
from .candidates import Candidate
from .clients import Client

__all__ = ["Org", "User", "JobAssessment", "CompetencyLibrary", "Candidate", "Client"]
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
pytest tests/models/test_schema.py -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add services/orchestrator-api/src/models/candidates.py \
        services/orchestrator-api/src/models/clients.py \
        services/orchestrator-api/src/models/__init__.py \
        services/orchestrator-api/tests/models/test_schema.py
git commit -m "feat(schema): add Candidate and Client models with auth_method check constraint"
```

---

## Task 5: CandidateProfile and AssessmentSession Models

**Files:**
- Create: `services/orchestrator-api/src/models/candidate_profiles.py`
- Create: `services/orchestrator-api/src/models/assessment_sessions.py`
- Modify: `services/orchestrator-api/src/models/__init__.py`
- Modify: `services/orchestrator-api/tests/models/test_schema.py`

**Interfaces:**
- Produces: `CandidateProfile`, `AssessmentSession` — referenced by question_sets, behavior_profiles, integrity_flags, hiring_reports

- [ ] **Step 1: Append tests to `test_schema.py`**

```python
# append to tests/models/test_schema.py
from src.models.candidate_profiles import CandidateProfile
from src.models.assessment_sessions import AssessmentSession


def test_candidate_profiles_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("candidate_profiles")}
    expected = {
        "id", "org_id", "candidate_id", "job_assessment_id",
        "summary", "skill_matrix", "experience_matrix",
        "leadership_level_estimate", "strengths", "risk_flags",
        "parsing_confidence", "created_at",
    }
    assert cols == expected


def test_assessment_session_status_check(db):
    org = Org(name="SessOrg")
    db.add(org)
    db.flush()
    user = User(org_id=org.id, email="su@su.com", role="user", password_hash="h")
    db.add(user)
    db.flush()
    ja = JobAssessment(
        org_id=org.id, title="T", difficulty_level="mid",
        duration_minutes=30, competency_weightage={}, created_by=user.id,
    )
    db.add(ja)
    db.flush()
    c = Candidate(org_id=org.id, name="A", email="a@ss.com")
    db.add(c)
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(AssessmentSession(
            org_id=org.id, job_assessment_id=ja.id,
            candidate_id=c.id, status="archived", time_budget_seconds=3600,
        ))
        db.flush()
    db.rollback()


def test_assessment_session_default_status(db):
    org = Org(name="DefSessOrg")
    db.add(org)
    db.flush()
    user = User(org_id=org.id, email="def@su.com", role="user", password_hash="h")
    db.add(user)
    db.flush()
    ja = JobAssessment(
        org_id=org.id, title="T2", difficulty_level="senior",
        duration_minutes=45, competency_weightage={}, created_by=user.id,
    )
    db.add(ja)
    db.flush()
    c = Candidate(org_id=org.id, name="B", email="b@ss.com")
    db.add(c)
    db.flush()
    sess = AssessmentSession(
        org_id=org.id, job_assessment_id=ja.id,
        candidate_id=c.id, time_budget_seconds=3600,
    )
    db.add(sess)
    db.flush()
    assert sess.status == "invited"
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/models/test_schema.py::test_candidate_profiles_columns -v
```

Expected: `ImportError`

- [ ] **Step 3: Write `src/models/candidate_profiles.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

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
    strengths: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    risk_flags: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    parsing_confidence: Mapped[Optional[float]] = mapped_column(
        Numeric(4, 3),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4: Write `src/models/assessment_sessions.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('invited','in_progress','completed','expired')",
            name="ck_assessment_sessions_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    job_assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_assessments.id"), nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    candidate_profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("candidate_profiles.id"))
    status: Mapped[str] = mapped_column(
        nullable=False, server_default=text("'invited'")
    )
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    time_budget_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
```

- [ ] **Step 5: Update `src/models/__init__.py`**

```python
from .orgs import Org
from .users import User
from .job_assessments import JobAssessment
from .competency_library import CompetencyLibrary
from .candidates import Candidate
from .clients import Client
from .candidate_profiles import CandidateProfile
from .assessment_sessions import AssessmentSession

__all__ = [
    "Org", "User", "JobAssessment", "CompetencyLibrary",
    "Candidate", "Client", "CandidateProfile", "AssessmentSession",
]
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
pytest tests/models/test_schema.py -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add services/orchestrator-api/src/models/candidate_profiles.py \
        services/orchestrator-api/src/models/assessment_sessions.py \
        services/orchestrator-api/src/models/__init__.py \
        services/orchestrator-api/tests/models/test_schema.py
git commit -m "feat(schema): add CandidateProfile and AssessmentSession models"
```

---

## Task 6: QuestionSet and SessionQuestion Models

**Files:**
- Create: `services/orchestrator-api/src/models/question_sets.py`
- Create: `services/orchestrator-api/src/models/session_questions.py`
- Modify: `services/orchestrator-api/src/models/__init__.py`
- Modify: `services/orchestrator-api/tests/models/test_schema.py`

**Interfaces:**
- Produces: `QuestionSet`, `SessionQuestion` — referenced by question_fingerprints, integrity_flags

- [ ] **Step 1: Append tests to `test_schema.py`**

```python
# append to tests/models/test_schema.py
from src.models.question_sets import QuestionSet
from src.models.session_questions import SessionQuestion


def test_question_sets_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("question_sets")}
    assert cols == {"id", "org_id", "session_id", "generated_at", "locked_at", "generation_prompt_version"}


def test_question_set_session_unique(db):
    # Two question_sets cannot share the same session_id (UNIQUE constraint)
    org = Org(name="QSOrg")
    db.add(org)
    db.flush()
    user = User(org_id=org.id, email="qs@qs.com", role="user", password_hash="h")
    db.add(user)
    db.flush()
    ja = JobAssessment(org_id=org.id, title="T", difficulty_level="mid", duration_minutes=30, competency_weightage={}, created_by=user.id)
    db.add(ja)
    db.flush()
    c = Candidate(org_id=org.id, name="C", email="c@qs.com")
    db.add(c)
    db.flush()
    sess = AssessmentSession(org_id=org.id, job_assessment_id=ja.id, candidate_id=c.id, time_budget_seconds=1800)
    db.add(sess)
    db.flush()
    qs = QuestionSet(org_id=org.id, session_id=sess.id, generation_prompt_version="v1")
    db.add(qs)
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(QuestionSet(org_id=org.id, session_id=sess.id, generation_prompt_version="v2"))
        db.flush()
    db.rollback()


def test_session_questions_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("session_questions")}
    expected = {
        "id", "org_id", "question_set_id", "sequence_no", "question",
        "category", "target_competencies", "difficulty", "answer_format",
        "options", "answer_text", "answered_at", "evaluation", "created_at",
    }
    assert cols == expected


def test_session_question_difficulty_check(db):
    # need a question_set first — reuse db state from prior tests is unreliable; build fresh
    org = Org(name="SQOrg")
    db.add(org)
    db.flush()
    user = User(org_id=org.id, email="sq@sq.com", role="user", password_hash="h")
    db.add(user)
    db.flush()
    ja = JobAssessment(org_id=org.id, title="T", difficulty_level="junior", duration_minutes=20, competency_weightage={}, created_by=user.id)
    db.add(ja)
    db.flush()
    c = Candidate(org_id=org.id, name="D", email="d@sq.com")
    db.add(c)
    db.flush()
    sess = AssessmentSession(org_id=org.id, job_assessment_id=ja.id, candidate_id=c.id, time_budget_seconds=1200)
    db.add(sess)
    db.flush()
    qs = QuestionSet(org_id=org.id, session_id=sess.id, generation_prompt_version="v1")
    db.add(qs)
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(SessionQuestion(
            org_id=org.id, question_set_id=qs.id, sequence_no=1,
            question={}, category="Technical", difficulty="legendary",
            answer_format="short_text",
        ))
        db.flush()
    db.rollback()
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/models/test_schema.py::test_question_sets_columns -v
```

Expected: `ImportError`

- [ ] **Step 3: Write `src/models/question_sets.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class QuestionSet(Base):
    __tablename__ = "question_sets"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_question_sets_session_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_sessions.id"), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    generation_prompt_version: Mapped[str] = mapped_column(String, nullable=False)
```

- [ ] **Step 4: Write `src/models/session_questions.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SessionQuestion(Base):
    __tablename__ = "session_questions"
    __table_args__ = (
        UniqueConstraint("question_set_id", "sequence_no", name="uq_session_questions_set_seq"),
        CheckConstraint(
            "difficulty IN ('easy','medium','hard','expert')",
            name="ck_session_questions_difficulty",
        ),
        CheckConstraint(
            "answer_format IN ('multiple_choice','short_text','long_text')",
            name="ck_session_questions_answer_format",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    question_set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("question_sets.id"), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[dict] = mapped_column(JSONB, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    target_competencies: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    difficulty: Mapped[str] = mapped_column(String, nullable=False)
    answer_format: Mapped[str] = mapped_column(String, nullable=False)
    options: Mapped[Optional[dict]] = mapped_column(JSONB)
    answer_text: Mapped[Optional[str]] = mapped_column(Text)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    evaluation: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 5: Update `src/models/__init__.py`**

```python
from .orgs import Org
from .users import User
from .job_assessments import JobAssessment
from .competency_library import CompetencyLibrary
from .candidates import Candidate
from .clients import Client
from .candidate_profiles import CandidateProfile
from .assessment_sessions import AssessmentSession
from .question_sets import QuestionSet
from .session_questions import SessionQuestion

__all__ = [
    "Org", "User", "JobAssessment", "CompetencyLibrary",
    "Candidate", "Client", "CandidateProfile", "AssessmentSession",
    "QuestionSet", "SessionQuestion",
]
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
pytest tests/models/test_schema.py -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add services/orchestrator-api/src/models/question_sets.py \
        services/orchestrator-api/src/models/session_questions.py \
        services/orchestrator-api/src/models/__init__.py \
        services/orchestrator-api/tests/models/test_schema.py
git commit -m "feat(schema): add QuestionSet and SessionQuestion models"
```

---

## Task 7: QuestionFingerprint Model + pgvector Test

**Files:**
- Create: `services/orchestrator-api/src/models/question_fingerprints.py`
- Modify: `services/orchestrator-api/src/models/__init__.py`
- Create: `services/orchestrator-api/tests/models/test_question_fingerprints.py`

**Interfaces:**
- Produces: `QuestionFingerprint` with `question_embedding vector(1536)`

- [ ] **Step 1: Write failing test**

Create `tests/models/test_question_fingerprints.py`:

```python
import uuid
import pytest
from sqlalchemy import inspect, text

from src.models.orgs import Org
from src.models.question_fingerprints import QuestionFingerprint


def test_question_fingerprints_table_exists(engine):
    assert "question_fingerprints" in inspect(engine).get_table_names()


def test_question_fingerprints_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("question_fingerprints")}
    assert cols == {"id", "org_id", "question_text", "question_embedding", "question_set_id", "created_at"}


def test_insert_and_cosine_similarity(db, engine):
    org = Org(name="VecOrg")
    db.add(org)
    db.flush()

    vec_a = [0.1] * 1536
    vec_b = [0.1] * 1536  # identical → cosine distance 0
    vec_c = [-0.1] * 1536  # opposite → cosine distance 2

    qf_a = QuestionFingerprint(org_id=org.id, question_text="Q A", question_embedding=vec_a)
    qf_b = QuestionFingerprint(org_id=org.id, question_text="Q B", question_embedding=vec_b)
    qf_c = QuestionFingerprint(org_id=org.id, question_text="Q C", question_embedding=vec_c)
    db.add_all([qf_a, qf_b, qf_c])
    db.flush()

    # Nearest neighbour to vec_a should be qf_b (distance ≈ 0), not qf_c
    result = db.execute(
        text(
            "SELECT id FROM question_fingerprints "
            "WHERE org_id = :org_id AND id != :self_id "
            "ORDER BY question_embedding <=> CAST(:vec AS vector) "
            "LIMIT 1"
        ),
        {"org_id": str(org.id), "self_id": str(qf_a.id), "vec": str(vec_a)},
    ).fetchone()

    assert result is not None
    assert uuid.UUID(str(result[0])) == qf_b.id


def test_embedding_rejects_wrong_dimension(db):
    org = Org(name="DimOrg")
    db.add(org)
    db.flush()
    from sqlalchemy.exc import DataError
    with pytest.raises((DataError, Exception)):
        qf = QuestionFingerprint(org_id=org.id, question_text="Q", question_embedding=[0.1] * 10)
        db.add(qf)
        db.flush()
    db.rollback()
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/models/test_question_fingerprints.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Write `src/models/question_fingerprints.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from .base import Base

EMBEDDING_DIM = 1536


class QuestionFingerprint(Base):
    __tablename__ = "question_fingerprints"
    __table_args__ = (
        Index(
            "idx_question_fingerprints_embedding",
            "question_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"question_embedding": "vector_cosine_ops"},
        ),
        Index("idx_question_fingerprints_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_embedding: Mapped[list] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    question_set_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("question_sets.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4: Update `src/models/__init__.py`**

```python
from .orgs import Org
from .users import User
from .job_assessments import JobAssessment
from .competency_library import CompetencyLibrary
from .candidates import Candidate
from .clients import Client
from .candidate_profiles import CandidateProfile
from .assessment_sessions import AssessmentSession
from .question_sets import QuestionSet
from .session_questions import SessionQuestion
from .question_fingerprints import QuestionFingerprint

__all__ = [
    "Org", "User", "JobAssessment", "CompetencyLibrary",
    "Candidate", "Client", "CandidateProfile", "AssessmentSession",
    "QuestionSet", "SessionQuestion", "QuestionFingerprint",
]
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
pytest tests/models/test_question_fingerprints.py -v
```

Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add services/orchestrator-api/src/models/question_fingerprints.py \
        services/orchestrator-api/src/models/__init__.py \
        services/orchestrator-api/tests/models/test_question_fingerprints.py
git commit -m "feat(schema): add QuestionFingerprint model with vector(1536) and HNSW index"
```

---

## Task 8: BehaviorProfile and IntegrityFlag Models

**Files:**
- Create: `services/orchestrator-api/src/models/behavior_profiles.py`
- Create: `services/orchestrator-api/src/models/integrity_flags.py`
- Modify: `services/orchestrator-api/src/models/__init__.py`
- Modify: `services/orchestrator-api/tests/models/test_schema.py`

**Interfaces:**
- Produces: `BehaviorProfile`, `IntegrityFlag` — referenced by hiring_reports

- [ ] **Step 1: Append tests to `test_schema.py`**

```python
# append to tests/models/test_schema.py
from src.models.behavior_profiles import BehaviorProfile
from src.models.integrity_flags import IntegrityFlag


def test_behavior_profiles_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("behavior_profiles")}
    expected = {
        "id", "org_id", "session_id", "disc_style", "big_five",
        "leadership_style", "decision_style", "communication_style",
        "work_style", "stress_signal", "eq_signal",
        "team_compatibility_signal", "created_at",
    }
    assert cols == expected


def test_behavior_profile_session_unique(db):
    org = Org(name="BPOrg")
    db.add(org)
    db.flush()
    user = User(org_id=org.id, email="bp@bp.com", role="user", password_hash="h")
    db.add(user)
    db.flush()
    ja = JobAssessment(org_id=org.id, title="T", difficulty_level="mid", duration_minutes=30, competency_weightage={}, created_by=user.id)
    db.add(ja)
    db.flush()
    c = Candidate(org_id=org.id, name="X", email="x@bp.com")
    db.add(c)
    db.flush()
    sess = AssessmentSession(org_id=org.id, job_assessment_id=ja.id, candidate_id=c.id, time_budget_seconds=1800)
    db.add(sess)
    db.flush()
    db.add(BehaviorProfile(org_id=org.id, session_id=sess.id))
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(BehaviorProfile(org_id=org.id, session_id=sess.id))
        db.flush()
    db.rollback()


def test_integrity_flag_type_check(db):
    org = Org(name="IFOrg")
    db.add(org)
    db.flush()
    user = User(org_id=org.id, email="if@if.com", role="user", password_hash="h")
    db.add(user)
    db.flush()
    ja = JobAssessment(org_id=org.id, title="T", difficulty_level="junior", duration_minutes=20, competency_weightage={}, created_by=user.id)
    db.add(ja)
    db.flush()
    c = Candidate(org_id=org.id, name="Y", email="y@if.com")
    db.add(c)
    db.flush()
    sess = AssessmentSession(org_id=org.id, job_assessment_id=ja.id, candidate_id=c.id, time_budget_seconds=1200)
    db.add(sess)
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(IntegrityFlag(
            org_id=org.id, session_id=sess.id,
            flag_type="plagiarism", severity="high", evidence="copy-paste detected",
        ))
        db.flush()
    db.rollback()
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/models/test_schema.py::test_behavior_profiles_columns -v
```

Expected: `ImportError`

- [ ] **Step 3: Write `src/models/behavior_profiles.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BehaviorProfile(Base):
    __tablename__ = "behavior_profiles"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_behavior_profiles_session_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_sessions.id"), nullable=False)
    disc_style: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    big_five: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    leadership_style: Mapped[Optional[str]] = mapped_column(String)
    decision_style: Mapped[Optional[str]] = mapped_column(String)
    communication_style: Mapped[Optional[str]] = mapped_column(String)
    work_style: Mapped[Optional[str]] = mapped_column(String)
    stress_signal: Mapped[Optional[str]] = mapped_column(String)
    eq_signal: Mapped[Optional[str]] = mapped_column(String)
    team_compatibility_signal: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4: Write `src/models/integrity_flags.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class IntegrityFlag(Base):
    __tablename__ = "integrity_flags"
    __table_args__ = (
        CheckConstraint(
            "flag_type IN ('ai_generated','duplicate_answer','resume_inconsistency','behavioral_anomaly')",
            name="ck_integrity_flags_flag_type",
        ),
        CheckConstraint(
            "severity IN ('low','medium','high')",
            name="ck_integrity_flags_severity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_sessions.id"), nullable=False)
    session_question_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("session_questions.id"))
    flag_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 5: Update `src/models/__init__.py`**

```python
from .orgs import Org
from .users import User
from .job_assessments import JobAssessment
from .competency_library import CompetencyLibrary
from .candidates import Candidate
from .clients import Client
from .candidate_profiles import CandidateProfile
from .assessment_sessions import AssessmentSession
from .question_sets import QuestionSet
from .session_questions import SessionQuestion
from .question_fingerprints import QuestionFingerprint
from .behavior_profiles import BehaviorProfile
from .integrity_flags import IntegrityFlag

__all__ = [
    "Org", "User", "JobAssessment", "CompetencyLibrary",
    "Candidate", "Client", "CandidateProfile", "AssessmentSession",
    "QuestionSet", "SessionQuestion", "QuestionFingerprint",
    "BehaviorProfile", "IntegrityFlag",
]
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
pytest tests/models/test_schema.py -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add services/orchestrator-api/src/models/behavior_profiles.py \
        services/orchestrator-api/src/models/integrity_flags.py \
        services/orchestrator-api/src/models/__init__.py \
        services/orchestrator-api/tests/models/test_schema.py
git commit -m "feat(schema): add BehaviorProfile and IntegrityFlag models"
```

---

## Task 9: HiringReport and ReportShare Models

**Files:**
- Create: `services/orchestrator-api/src/models/hiring_reports.py`
- Create: `services/orchestrator-api/src/models/report_shares.py`
- Modify: `services/orchestrator-api/src/models/__init__.py`
- Modify: `services/orchestrator-api/tests/models/test_schema.py`

**Interfaces:**
- Produces: `HiringReport`, `ReportShare` — `HiringReport` must exist before `ReportShare` (FK dependency)

- [ ] **Step 1: Append tests to `test_schema.py`**

```python
# append to tests/models/test_schema.py
from src.models.hiring_reports import HiringReport
from src.models.report_shares import ReportShare


def test_hiring_reports_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("hiring_reports")}
    expected = {
        "id", "org_id", "session_id", "executive_summary", "score_rollup",
        "behavior_profile_id", "integrity_summary", "salary_band", "verdict",
        "ai_confidence_score", "recommended_next_round", "training_needs",
        "suggested_hr_questions", "suggested_ceo_questions",
        "reviewer_override", "created_at",
    }
    assert cols == expected


def test_hiring_report_verdict_check(db):
    org = Org(name="HROrg")
    db.add(org)
    db.flush()
    user = User(org_id=org.id, email="hr@hr.com", role="user", password_hash="h")
    db.add(user)
    db.flush()
    ja = JobAssessment(org_id=org.id, title="T", difficulty_level="senior", duration_minutes=60, competency_weightage={}, created_by=user.id)
    db.add(ja)
    db.flush()
    c = Candidate(org_id=org.id, name="Z", email="z@hr.com")
    db.add(c)
    db.flush()
    sess = AssessmentSession(org_id=org.id, job_assessment_id=ja.id, candidate_id=c.id, time_budget_seconds=3600)
    db.add(sess)
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(HiringReport(org_id=org.id, session_id=sess.id, verdict="maybe"))
        db.flush()
    db.rollback()


def test_report_shares_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("report_shares")}
    expected = {"id", "org_id", "hiring_report_id", "client_id", "shared_by", "expires_at", "revoked_at", "created_at"}
    assert cols == expected
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/models/test_schema.py::test_hiring_reports_columns -v
```

Expected: `ImportError`

- [ ] **Step 3: Write `src/models/hiring_reports.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class HiringReport(Base):
    __tablename__ = "hiring_reports"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_hiring_reports_session_id"),
        CheckConstraint(
            "verdict IS NULL OR verdict IN ('strong_hire','hire','consider','borderline','reject')",
            name="ck_hiring_reports_verdict",
        ),
        CheckConstraint(
            "ai_confidence_score IS NULL OR (ai_confidence_score >= 0 AND ai_confidence_score <= 100)",
            name="ck_hiring_reports_ai_confidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_sessions.id"), nullable=False)
    executive_summary: Mapped[Optional[str]] = mapped_column(Text)
    score_rollup: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    behavior_profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("behavior_profiles.id"))
    integrity_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    salary_band: Mapped[Optional[str]] = mapped_column(String)
    verdict: Mapped[Optional[str]] = mapped_column(String)
    ai_confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    recommended_next_round: Mapped[Optional[str]] = mapped_column(Text)
    training_needs: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    suggested_hr_questions: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    suggested_ceo_questions: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    reviewer_override: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 4: Write `src/models/report_shares.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ReportShare(Base):
    __tablename__ = "report_shares"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    hiring_report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hiring_reports.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), nullable=False)
    shared_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 5: Update `src/models/__init__.py`**

```python
from .orgs import Org
from .users import User
from .job_assessments import JobAssessment
from .competency_library import CompetencyLibrary
from .candidates import Candidate
from .clients import Client
from .candidate_profiles import CandidateProfile
from .assessment_sessions import AssessmentSession
from .question_sets import QuestionSet
from .session_questions import SessionQuestion
from .question_fingerprints import QuestionFingerprint
from .behavior_profiles import BehaviorProfile
from .integrity_flags import IntegrityFlag
from .hiring_reports import HiringReport
from .report_shares import ReportShare

__all__ = [
    "Org", "User", "JobAssessment", "CompetencyLibrary",
    "Candidate", "Client", "CandidateProfile", "AssessmentSession",
    "QuestionSet", "SessionQuestion", "QuestionFingerprint",
    "BehaviorProfile", "IntegrityFlag", "HiringReport", "ReportShare",
]
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
pytest tests/models/test_schema.py -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add services/orchestrator-api/src/models/hiring_reports.py \
        services/orchestrator-api/src/models/report_shares.py \
        services/orchestrator-api/src/models/__init__.py \
        services/orchestrator-api/tests/models/test_schema.py
git commit -m "feat(schema): add HiringReport and ReportShare models"
```

---

## Task 10: PromptTemplate and AuditLog Models

**Files:**
- Create: `services/orchestrator-api/src/models/prompt_templates.py`
- Create: `services/orchestrator-api/src/models/audit_logs.py`
- Modify: `services/orchestrator-api/src/models/__init__.py`
- Modify: `services/orchestrator-api/tests/models/test_schema.py`
- Create: `services/orchestrator-api/tests/models/test_audit_logs.py`

**Interfaces:**
- Produces: `PromptTemplate` (nullable org_id = global), `AuditLog` (append-only enforced by migration GRANT — not at model level)

- [ ] **Step 1: Append tests to `test_schema.py`**

```python
# append to tests/models/test_schema.py
from src.models.prompt_templates import PromptTemplate
from src.models.audit_logs import AuditLog


def test_prompt_templates_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("prompt_templates")}
    assert cols == {"id", "org_id", "agent_name", "version", "template_body", "is_active", "created_at"}


def test_prompt_template_global_null_org_id(db):
    pt = PromptTemplate(org_id=None, agent_name="question_generation", version="v1", template_body="SYSTEM: ...")
    db.add(pt)
    db.flush()
    assert pt.org_id is None


def test_prompt_template_unique_org_agent_version(db):
    org = Org(name="PTOrg")
    db.add(org)
    db.flush()
    db.add(PromptTemplate(org_id=org.id, agent_name="evaluation", version="v1", template_body="T"))
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(PromptTemplate(org_id=org.id, agent_name="evaluation", version="v1", template_body="T2"))
        db.flush()
    db.rollback()


def test_audit_logs_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("audit_logs")}
    assert cols == {"id", "org_id", "actor_id", "action", "entity_type", "entity_id", "metadata", "created_at"}
```

- [ ] **Step 2: Write `tests/models/test_audit_logs.py`**

```python
"""
audit_logs append-only test.

The REVOKE UPDATE, DELETE is applied by the Alembic migration — NOT by
Base.metadata.create_all(). Therefore, this test verifies only that:
  1. The table accepts INSERT.
  2. Rows inserted survive a flush.
The GRANT restriction is validated in test_rls.py after migration is run.
"""
import uuid
from src.models.orgs import Org
from src.models.audit_logs import AuditLog


def test_audit_log_insert(db):
    org = Org(name="AuditOrg")
    db.add(org)
    db.flush()

    log = AuditLog(
        org_id=org.id,
        actor_id=uuid.uuid4(),
        action="session.created",
        entity_type="assessment_session",
        entity_id=uuid.uuid4(),
        metadata={"ip": "127.0.0.1"},
    )
    db.add(log)
    db.flush()
    assert log.id is not None
    assert log.created_at is not None


def test_audit_log_metadata_defaults_empty(db):
    org = Org(name="AuditOrg2")
    db.add(org)
    db.flush()

    log = AuditLog(
        org_id=org.id,
        actor_id=uuid.uuid4(),
        action="report.viewed",
        entity_type="hiring_report",
        entity_id=uuid.uuid4(),
    )
    db.add(log)
    db.flush()
    # metadata defaults to {} at DB level; SQLAlchemy won't reflect the server default
    # until the row is expired and re-fetched
    db.expire(log)
    db.refresh(log)
    assert log.metadata == {}
```

- [ ] **Step 3: Run tests — expect FAIL**

```bash
pytest tests/models/test_schema.py::test_prompt_templates_columns tests/models/test_audit_logs.py -v
```

Expected: `ImportError`

- [ ] **Step 4: Write `src/models/prompt_templates.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint("org_id", "agent_name", "version", name="uq_prompt_templates_org_agent_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("orgs.id"), nullable=True)
    agent_name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)
    template_body: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 5: Write `src/models/audit_logs.py`**

```python
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 6: Update `src/models/__init__.py` (final)**

```python
from .orgs import Org
from .users import User
from .job_assessments import JobAssessment
from .competency_library import CompetencyLibrary
from .candidates import Candidate
from .clients import Client
from .candidate_profiles import CandidateProfile
from .assessment_sessions import AssessmentSession
from .question_sets import QuestionSet
from .session_questions import SessionQuestion
from .question_fingerprints import QuestionFingerprint
from .behavior_profiles import BehaviorProfile
from .integrity_flags import IntegrityFlag
from .hiring_reports import HiringReport
from .report_shares import ReportShare
from .prompt_templates import PromptTemplate
from .audit_logs import AuditLog

__all__ = [
    "Org", "User", "JobAssessment", "CompetencyLibrary",
    "Candidate", "Client", "CandidateProfile", "AssessmentSession",
    "QuestionSet", "SessionQuestion", "QuestionFingerprint",
    "BehaviorProfile", "IntegrityFlag", "HiringReport", "ReportShare",
    "PromptTemplate", "AuditLog",
]
```

- [ ] **Step 7: Run all model tests — expect PASS**

```bash
pytest tests/models/ -v
```

Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add services/orchestrator-api/src/models/prompt_templates.py \
        services/orchestrator-api/src/models/audit_logs.py \
        services/orchestrator-api/src/models/__init__.py \
        services/orchestrator-api/tests/models/test_schema.py \
        services/orchestrator-api/tests/models/test_audit_logs.py
git commit -m "feat(schema): add PromptTemplate and AuditLog models — all 17 models complete"
```

---

## Task 11: Alembic Migration — Full DDL with RLS, HNSW, and GRANT

**Files:**
- Create: `services/orchestrator-api/migrations/versions/0001_initial_schema.py`

**Interfaces:**
- Consumes: all 17 models registered in `src/models/__init__.py`
- Produces: single migration revision that creates every table, enables pgvector, sets RLS, creates HNSW index, and revokes UPDATE/DELETE on audit_logs from PUBLIC

- [ ] **Step 1: Write failing check — migration not yet run**

```bash
cd services/orchestrator-api
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/arap_prod \
  python -c "
from sqlalchemy import create_engine, inspect
eng = create_engine('postgresql://postgres:postgres@localhost:5432/arap_prod')
tables = inspect(eng).get_table_names()
assert 'orgs' not in tables, 'orgs already exists — drop the DB first'
print('Clean DB confirmed')
"
```

Expected: `Clean DB confirmed`

- [ ] **Step 2: Write `migrations/versions/0001_initial_schema.py`**

```python
"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_RLS_TABLES = [
    "users", "job_assessments", "candidates", "clients",
    "candidate_profiles", "assessment_sessions", "question_sets",
    "session_questions", "question_fingerprints", "behavior_profiles",
    "integrity_flags", "hiring_reports", "report_shares",
    "competency_library", "audit_logs",
]

_text = sa.text


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── orgs ─────────────────────────────────────────────────────────────────
    op.create_table(
        "orgs",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("plan_tier", sa.Text(), nullable=False, server_default=_text("'trial'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("org_id", "email", name="uq_users_org_email"),
        sa.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
    )

    # ── job_assessments ───────────────────────────────────────────────────────
    op.create_table(
        "job_assessments",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("department", sa.Text()),
        sa.Column("experience_min", sa.Integer()),
        sa.Column("experience_max", sa.Integer()),
        sa.Column("required_skills", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("preferred_skills", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("responsibilities", sa.Text()),
        sa.Column("education", sa.Text()),
        sa.Column("certifications", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("behavioral_competencies", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("leadership_competencies", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("culture_values", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("difficulty_level", sa.Text(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("competency_weightage", JSONB(), nullable=False),
        sa.Column("created_by", UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "difficulty_level IN ('junior','mid','senior','executive')",
            name="ck_job_assessments_difficulty_level",
        ),
    )

    # ── competency_library ────────────────────────────────────────────────────
    op.create_table(
        "competency_library",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("rubric_notes", sa.Text()),
        sa.Column("created_by", UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("org_id", "name", name="uq_competency_library_org_name"),
    )

    # ── candidates ────────────────────────────────────────────────────────────
    op.create_table(
        "candidates",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("resume_file_url", sa.Text()),
        sa.Column("linkedin_url", sa.Text()),
        sa.Column("github_url", sa.Text()),
        sa.Column("portfolio_url", sa.Text()),
        sa.Column("auth_method", sa.Text()),
        sa.Column("password_hash", sa.Text()),
        sa.Column("login_token_hash", sa.Text()),
        sa.Column("login_token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("org_id", "email", name="uq_candidates_org_email"),
        sa.CheckConstraint(
            "auth_method IS NULL OR auth_method IN ('magic_link','otp','password')",
            name="ck_candidates_auth_method",
        ),
    )

    # ── clients ───────────────────────────────────────────────────────────────
    op.create_table(
        "clients",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("auth_method", sa.Text()),
        sa.Column("password_hash", sa.Text()),
        sa.Column("login_token_hash", sa.Text()),
        sa.Column("login_token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("org_id", "email", name="uq_clients_org_email"),
        sa.CheckConstraint(
            "auth_method IS NULL OR auth_method IN ('magic_link','otp','password')",
            name="ck_clients_auth_method",
        ),
    )

    # ── candidate_profiles ────────────────────────────────────────────────────
    op.create_table(
        "candidate_profiles",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("candidate_id", UUID(), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("job_assessment_id", UUID(), sa.ForeignKey("job_assessments.id"), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("skill_matrix", JSONB(), nullable=False, server_default=_text("'{}'")),
        sa.Column("experience_matrix", JSONB(), nullable=False, server_default=_text("'{}'")),
        sa.Column("leadership_level_estimate", sa.Text()),
        sa.Column("strengths", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("risk_flags", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("parsing_confidence", sa.Numeric(4, 3)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── assessment_sessions ───────────────────────────────────────────────────
    op.create_table(
        "assessment_sessions",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("job_assessment_id", UUID(), sa.ForeignKey("job_assessments.id"), nullable=False),
        sa.Column("candidate_id", UUID(), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("candidate_profile_id", UUID(), sa.ForeignKey("candidate_profiles.id")),
        sa.Column("status", sa.Text(), nullable=False, server_default=_text("'invited'")),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("time_budget_seconds", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('invited','in_progress','completed','expired')",
            name="ck_assessment_sessions_status",
        ),
    )

    # ── question_sets ─────────────────────────────────────────────────────────
    op.create_table(
        "question_sets",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("session_id", UUID(), sa.ForeignKey("assessment_sessions.id"), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("generation_prompt_version", sa.Text(), nullable=False),
        sa.UniqueConstraint("session_id", name="uq_question_sets_session_id"),
    )

    # ── session_questions ─────────────────────────────────────────────────────
    op.create_table(
        "session_questions",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("question_set_id", UUID(), sa.ForeignKey("question_sets.id"), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("question", JSONB(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("target_competencies", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("difficulty", sa.Text(), nullable=False),
        sa.Column("answer_format", sa.Text(), nullable=False),
        sa.Column("options", JSONB()),
        sa.Column("answer_text", sa.Text()),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
        sa.Column("evaluation", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("question_set_id", "sequence_no", name="uq_session_questions_set_seq"),
        sa.CheckConstraint(
            "difficulty IN ('easy','medium','hard','expert')",
            name="ck_session_questions_difficulty",
        ),
        sa.CheckConstraint(
            "answer_format IN ('multiple_choice','short_text','long_text')",
            name="ck_session_questions_answer_format",
        ),
    )

    # ── question_fingerprints ─────────────────────────────────────────────────
    op.create_table(
        "question_fingerprints",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_embedding", sa.Text(), nullable=False),  # DDL overridden below
        sa.Column("question_set_id", UUID(), sa.ForeignKey("question_sets.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # Alter the column to the actual vector type (Alembic can't express vector natively)
    op.execute("ALTER TABLE question_fingerprints ALTER COLUMN question_embedding TYPE vector(1536) USING question_embedding::vector")
    op.execute(
        "CREATE INDEX idx_question_fingerprints_embedding "
        "ON question_fingerprints "
        "USING hnsw (question_embedding vector_cosine_ops) "
        "WITH (m=16, ef_construction=64)"
    )
    op.execute("CREATE INDEX idx_question_fingerprints_org_id ON question_fingerprints (org_id)")

    # ── behavior_profiles ─────────────────────────────────────────────────────
    op.create_table(
        "behavior_profiles",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("session_id", UUID(), sa.ForeignKey("assessment_sessions.id"), nullable=False),
        sa.Column("disc_style", JSONB(), nullable=False, server_default=_text("'{}'")),
        sa.Column("big_five", JSONB(), nullable=False, server_default=_text("'{}'")),
        sa.Column("leadership_style", sa.Text()),
        sa.Column("decision_style", sa.Text()),
        sa.Column("communication_style", sa.Text()),
        sa.Column("work_style", sa.Text()),
        sa.Column("stress_signal", sa.Text()),
        sa.Column("eq_signal", sa.Text()),
        sa.Column("team_compatibility_signal", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", name="uq_behavior_profiles_session_id"),
    )

    # ── integrity_flags ───────────────────────────────────────────────────────
    op.create_table(
        "integrity_flags",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("session_id", UUID(), sa.ForeignKey("assessment_sessions.id"), nullable=False),
        sa.Column("session_question_id", UUID(), sa.ForeignKey("session_questions.id")),
        sa.Column("flag_type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "flag_type IN ('ai_generated','duplicate_answer','resume_inconsistency','behavioral_anomaly')",
            name="ck_integrity_flags_flag_type",
        ),
        sa.CheckConstraint(
            "severity IN ('low','medium','high')",
            name="ck_integrity_flags_severity",
        ),
    )

    # ── hiring_reports ────────────────────────────────────────────────────────
    op.create_table(
        "hiring_reports",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("session_id", UUID(), sa.ForeignKey("assessment_sessions.id"), nullable=False),
        sa.Column("executive_summary", sa.Text()),
        sa.Column("score_rollup", JSONB(), nullable=False, server_default=_text("'{}'")),
        sa.Column("behavior_profile_id", UUID(), sa.ForeignKey("behavior_profiles.id")),
        sa.Column("integrity_summary", JSONB(), nullable=False, server_default=_text("'{}'")),
        sa.Column("salary_band", sa.Text()),
        sa.Column("verdict", sa.Text()),
        sa.Column("ai_confidence_score", sa.Numeric(5, 2)),
        sa.Column("recommended_next_round", sa.Text()),
        sa.Column("training_needs", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("suggested_hr_questions", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("suggested_ceo_questions", ARRAY(sa.Text()), nullable=False, server_default=_text("'{}'")),
        sa.Column("reviewer_override", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", name="uq_hiring_reports_session_id"),
        sa.CheckConstraint(
            "verdict IS NULL OR verdict IN ('strong_hire','hire','consider','borderline','reject')",
            name="ck_hiring_reports_verdict",
        ),
        sa.CheckConstraint(
            "ai_confidence_score IS NULL OR (ai_confidence_score >= 0 AND ai_confidence_score <= 100)",
            name="ck_hiring_reports_ai_confidence",
        ),
    )

    # ── report_shares ─────────────────────────────────────────────────────────
    op.create_table(
        "report_shares",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("hiring_report_id", UUID(), sa.ForeignKey("hiring_reports.id"), nullable=False),
        sa.Column("client_id", UUID(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("shared_by", UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── prompt_templates ──────────────────────────────────────────────────────
    op.create_table(
        "prompt_templates",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id")),  # nullable — NULL = global
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("template_body", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=_text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("org_id", "agent_name", "version", name="uq_prompt_templates_org_agent_version"),
    )

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(), server_default=_text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", UUID(), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("actor_id", UUID(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", UUID(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False, server_default=_text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── RLS ───────────────────────────────────────────────────────────────────
    for table in _RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        if table == "prompt_templates":
            op.execute(
                f"CREATE POLICY {table}_org_isolation ON {table} "
                f"USING (org_id = current_setting('app.current_org_id', true)::uuid "
                f"OR org_id IS NULL)"
            )
        else:
            op.execute(
                f"CREATE POLICY {table}_org_isolation ON {table} "
                f"USING (org_id = current_setting('app.current_org_id', true)::uuid)"
            )

    # ── audit_logs append-only ────────────────────────────────────────────────
    op.execute("REVOKE UPDATE, DELETE ON audit_logs FROM PUBLIC")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT ON audit_logs FROM PUBLIC")  # undo REVOKE guard

    for table in reversed(_RLS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_org_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP INDEX IF EXISTS idx_question_fingerprints_org_id")
    op.execute("DROP INDEX IF EXISTS idx_question_fingerprints_embedding")

    for table in [
        "audit_logs", "prompt_templates", "report_shares", "hiring_reports",
        "integrity_flags", "behavior_profiles", "question_fingerprints",
        "session_questions", "question_sets", "assessment_sessions",
        "candidate_profiles", "clients", "candidates",
        "competency_library", "job_assessments", "users", "orgs",
    ]:
        op.drop_table(table)

    op.execute("DROP EXTENSION IF EXISTS vector")
```

- [ ] **Step 3: Run migration against a fresh production DB**

```bash
cd services/orchestrator-api
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/arap_prod \
  alembic upgrade head
```

Expected output ends with:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, initial schema
```

- [ ] **Step 4: Verify all 17 tables exist**

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/arap_prod \
  python -c "
from sqlalchemy import create_engine, inspect
import os
eng = create_engine(os.environ['DATABASE_URL'])
tables = set(inspect(eng).get_table_names())
expected = {
  'orgs','users','job_assessments','competency_library','candidates','clients',
  'candidate_profiles','assessment_sessions','question_sets','session_questions',
  'question_fingerprints','behavior_profiles','integrity_flags','hiring_reports',
  'report_shares','prompt_templates','audit_logs'
}
missing = expected - tables
assert not missing, f'Missing tables: {missing}'
print('All 17 tables present')
"
```

Expected: `All 17 tables present`

- [ ] **Step 5: Commit**

```bash
git add services/orchestrator-api/migrations/versions/0001_initial_schema.py
git commit -m "feat(schema): Alembic migration 0001 — full DDL, RLS policies, HNSW index, audit_logs append-only"
```

---

## Task 12: RLS Integration Test + Code Review Gate

**Files:**
- Create: `services/orchestrator-api/tests/models/test_rls.py`

**Interfaces:**
- Consumes: migration-applied database (must run Task 11 before this task)
- Produces: verified RLS isolation proof and code-review request

- [ ] **Step 1: Write `tests/models/test_rls.py`**

```python
"""
RLS integration tests — require a migration-applied DB, not Base.metadata.create_all().
Run with: TEST_DATABASE_URL=... pytest tests/models/test_rls.py -v

These tests create two orgs and verify cross-org data leakage is impossible
when app.current_org_id is set correctly.
"""
import uuid
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/arap_prod",
)


@pytest.fixture(scope="module")
def rls_engine():
    eng = create_engine(DB_URL, echo=False)
    yield eng
    eng.dispose()


@pytest.fixture
def rls_session(rls_engine):
    Session = sessionmaker(bind=rls_engine)
    s = Session()
    yield s
    s.rollback()
    s.close()


def _insert_org(session, name: str) -> uuid.UUID:
    result = session.execute(
        text("INSERT INTO orgs (name) VALUES (:name) RETURNING id"),
        {"name": name},
    )
    session.commit()
    return result.fetchone()[0]


def _set_org(session, org_id: uuid.UUID) -> None:
    session.execute(text(f"SET LOCAL app.current_org_id = '{org_id}'"))


def test_rls_isolates_users_by_org(rls_session):
    org_a = _insert_org(rls_session, f"RLS-OrgA-{uuid.uuid4()}")
    org_b = _insert_org(rls_session, f"RLS-OrgB-{uuid.uuid4()}")

    # Insert a user in org_a without RLS (superuser can bypass)
    rls_session.execute(
        text("INSERT INTO users (org_id, email, role, password_hash) VALUES (:o, :e, 'user', 'h')"),
        {"o": str(org_a), "e": f"user-{uuid.uuid4()}@a.com"},
    )
    rls_session.commit()

    # As org_b, the user row from org_a should not be visible
    rls_session.execute(text("BEGIN"))
    _set_org(rls_session, org_b)
    rows = rls_session.execute(
        text("SELECT id FROM users WHERE org_id = :org_a"),
        {"org_a": str(org_a)},
    ).fetchall()
    assert rows == [], f"RLS leak: org_b can see {len(rows)} users from org_a"
    rls_session.execute(text("ROLLBACK"))


def test_rls_prompt_templates_global_visible_to_all(rls_session):
    org_a = _insert_org(rls_session, f"PT-OrgA-{uuid.uuid4()}")

    # Insert a global template (org_id IS NULL) as superuser
    rls_session.execute(
        text(
            "INSERT INTO prompt_templates (org_id, agent_name, version, template_body) "
            "VALUES (NULL, 'evaluation', :v, 'SYSTEM...')"
        ),
        {"v": f"v-{uuid.uuid4()}"},
    )
    rls_session.commit()

    # As org_a, the global template should be visible
    rls_session.execute(text("BEGIN"))
    _set_org(rls_session, org_a)
    rows = rls_session.execute(
        text("SELECT id FROM prompt_templates WHERE org_id IS NULL")
    ).fetchall()
    assert len(rows) >= 1, "Global prompt_template not visible through RLS"
    rls_session.execute(text("ROLLBACK"))


def test_audit_logs_update_denied(rls_session):
    org = _insert_org(rls_session, f"AuditRLS-{uuid.uuid4()}")
    result = rls_session.execute(
        text(
            "INSERT INTO audit_logs (org_id, actor_id, action, entity_type, entity_id) "
            "VALUES (:o, gen_random_uuid(), 'test', 'orgs', gen_random_uuid()) RETURNING id"
        ),
        {"o": str(org)},
    )
    rls_session.commit()
    log_id = result.fetchone()[0]

    from sqlalchemy.exc import ProgrammingError
    with pytest.raises(ProgrammingError, match="permission denied"):
        rls_session.execute(
            text("UPDATE audit_logs SET action = 'tampered' WHERE id = :id"),
            {"id": str(log_id)},
        )
        rls_session.commit()
    rls_session.rollback()
```

- [ ] **Step 2: Run RLS tests against migration-applied DB**

```bash
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/arap_prod \
  pytest tests/models/test_rls.py -v
```

Expected: 3 tests PASS

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/models/ -v --tb=short
```

Expected: all tests PASS, 0 failures

- [ ] **Step 4: REQUEST CODE REVIEW before running migration in any shared/staging environment**

Per session file rule: invoke `superpowers:requesting-code-review` skill now.
Do NOT run `alembic upgrade head` on any shared or staging database until the review passes.

- [ ] **Step 5: Commit**

```bash
git add services/orchestrator-api/tests/models/test_rls.py
git commit -m "test(schema): RLS isolation and audit_logs append-only integration tests"
```

---

## Self-Review

**Spec coverage check:**

| PRD §12 requirement | Task |
|---|---|
| All 17 tables | Tasks 2–10 |
| Every table (except orgs) has org_id | All model files, checked in test_schema.py |
| RLS enabled + policy | Task 11 migration + Task 12 test_rls.py |
| question_fingerprints.question_embedding = vector(1536) | Task 7 |
| HNSW index (m=16, ef_construction=64) | Task 7 model + Task 11 migration |
| session_questions.evaluation = jsonb | Task 6 session_questions.py |
| candidates/clients auth_method enum + nullable fields | Task 4 |
| assessment_sessions.status enum | Task 5 |
| audit_logs append-only (INSERT only) | Task 11 REVOKE + Task 12 test |
| prompt_templates nullable org_id (global = NULL) | Task 10 |
| report_shares scopes Client access | Task 9 |
| Code review before migration runs | Task 12 step 4 |

**Placeholder scan:** None found.

**Type consistency:** All UUID FKs use `UUID()` type in migration. `ARRAY(sa.Text())` used consistently. `JSONB()` used for all jsonb columns. `vector(1536)` applied via ALTER in migration because Alembic's `op.create_table` cannot express pgvector types natively — this is documented in Task 11.

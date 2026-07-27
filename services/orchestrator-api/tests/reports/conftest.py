import os
import uuid as _uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
import src.models  # noqa: F401
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from src.models.assessment_sessions import AssessmentSession
from src.models.base import Base
from src.models.candidates import Candidate
from src.models.job_assessments import JobAssessment
from src.models.orgs import Org
from src.models.users import User
from src.modules.auth.token import create_access_token

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://arap:arap@localhost:5434/arap_test"
)


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
def report_seed(db: Session) -> dict:
    uid = _uuid.uuid4().hex[:8]
    org = Org(name=f"Report Test Org {uid}")
    db.add(org)
    db.flush()

    admin = User(
        org_id=org.id,
        email=f"admin-{uid}@test.com",
        role="admin",
        password_hash="x",
    )
    db.add(admin)
    db.flush()

    candidate = Candidate(
        org_id=org.id,
        name="Bob",
        email=f"bob-{uid}@example.com",
        auth_method="magic_link",
    )
    db.add(candidate)
    db.flush()

    job = JobAssessment(
        org_id=org.id,
        title="Product Manager",
        difficulty_level="mid",
        duration_minutes=45,
        competency_weightage={"problem_solving": 50.0, "communication": 50.0},
        created_by=admin.id,
    )
    db.add(job)
    db.flush()

    session = AssessmentSession(
        org_id=org.id,
        job_assessment_id=job.id,
        candidate_id=candidate.id,
        time_budget_seconds=2700,
        status="completed",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    db.add(session)
    db.flush()
    db.commit()

    db.refresh(org); db.refresh(admin); db.refresh(session)

    return {"org": org, "admin": admin, "candidate": candidate, "job": job, "session": session}


@pytest.fixture
def user_token(report_seed: dict) -> str:
    return create_access_token({
        "sub": str(report_seed["admin"].id),
        "role": "admin",
        "org_id": str(report_seed["org"].id),
    })


@pytest_asyncio.fixture
async def async_client(db: Session):
    from src.database import get_db
    from src.main import app
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

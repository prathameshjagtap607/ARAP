import os
from collections.abc import Generator

import fakeredis
import pytest
import pytest_asyncio
import src.models  # noqa: F401 — registers all models
from httpx import ASGITransport, AsyncClient
from passlib.context import CryptContext
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from src.models.base import Base

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://arap:arap@localhost:5434/arap_test",
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
def db(engine) -> Generator[Session, None, None]:
    _Session = sessionmaker(engine)
    s = _Session()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def seed(db: Session) -> dict:
    from src.models.assessment_sessions import AssessmentSession
    from src.models.candidates import Candidate
    from src.models.clients import Client
    from src.models.hiring_reports import HiringReport
    from src.models.job_assessments import JobAssessment
    from src.models.orgs import Org
    from src.models.report_shares import ReportShare
    from src.models.users import User

    org = Org(name="Test Org")
    db.add(org)
    db.flush()

    admin = User(
        org_id=org.id,
        email="admin@test.com",
        role="admin",
        password_hash=pwd_context.hash("adminpass"),
    )
    user = User(
        org_id=org.id,
        email="user@test.com",
        role="user",
        password_hash=pwd_context.hash("userpass"),
    )
    db.add_all([admin, user])
    db.flush()

    candidate = Candidate(
        org_id=org.id,
        name="Alice",
        email="alice@example.com",
        auth_method="magic_link",
    )
    client = Client(
        org_id=org.id,
        name="Bob Corp",
        email="bob@client.com",
        auth_method="magic_link",
    )
    db.add_all([candidate, client])
    db.flush()

    job = JobAssessment(
        org_id=org.id,
        title="Engineer",
        department="Eng",
        difficulty_level="mid",
        duration_minutes=60,
        competency_weightage={},
        created_by=admin.id,
    )
    db.add(job)
    db.flush()

    session_a = AssessmentSession(
        org_id=org.id,
        job_assessment_id=job.id,
        candidate_id=candidate.id,
        time_budget_seconds=3600,
    )
    session_b = AssessmentSession(
        org_id=org.id,
        job_assessment_id=job.id,
        candidate_id=candidate.id,
        time_budget_seconds=3600,
    )
    db.add_all([session_a, session_b])
    db.flush()

    report = HiringReport(org_id=org.id, session_id=session_a.id)
    db.add(report)
    db.flush()

    share = ReportShare(
        org_id=org.id,
        hiring_report_id=report.id,
        client_id=client.id,
        shared_by=admin.id,
    )
    db.add(share)
    db.flush()

    db.commit()

    return {
        "org": org,
        "admin": admin,
        "user": user,
        "candidate": candidate,
        "client": client,
        "session_a": session_a,
        "session_b": session_b,
        "share": share,
    }


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

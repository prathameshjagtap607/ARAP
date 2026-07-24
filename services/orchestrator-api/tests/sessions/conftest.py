import os
import uuid as _uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

import src.models  # noqa: F401
from src.models.assessment_sessions import AssessmentSession
from src.models.base import Base
from src.models.candidates import Candidate
from src.models.job_assessments import JobAssessment
from src.models.orgs import Org
from src.models.question_sets import QuestionSet
from src.models.session_questions import SessionQuestion
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
def seed(db: Session) -> dict:
    uid = _uuid.uuid4().hex[:8]
    org = Org(name=f"Sessions Test Org {uid}")
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
        name="Alice",
        email=f"alice-{uid}@example.com",
        auth_method="magic_link",
    )
    db.add(candidate)
    db.flush()

    job = JobAssessment(
        org_id=org.id,
        title="Senior Engineer",
        department="Engineering",
        difficulty_level="senior",
        duration_minutes=30,
        competency_weightage={"problem_solving": 100.0},
        created_by=admin.id,
    )
    db.add(job)
    db.flush()

    session = AssessmentSession(
        org_id=org.id,
        job_assessment_id=job.id,
        candidate_id=candidate.id,
        time_budget_seconds=1800,
    )
    db.add(session)
    db.flush()

    # Locked question set with 2 questions
    qset = QuestionSet(
        org_id=org.id,
        session_id=session.id,
        generation_prompt_version="v1",
        locked_at=datetime.now(UTC),
    )
    db.add(qset)
    db.flush()

    q1 = SessionQuestion(
        org_id=org.id,
        question_set_id=qset.id,
        sequence_no=1,
        question={"text": "Describe your Python experience."},
        category="Technical",
        target_competencies=["problem_solving"],
        difficulty="medium",
        answer_format="long_text",
    )
    q2 = SessionQuestion(
        org_id=org.id,
        question_set_id=qset.id,
        sequence_no=2,
        question={"text": "What is 2+2?", "options": {"A": "3", "B": "4", "C": "5"}},
        category="Technical",
        target_competencies=["problem_solving"],
        difficulty="easy",
        answer_format="multiple_choice",
        options={"A": "3", "B": "4", "C": "5"},
    )
    db.add_all([q1, q2])
    db.commit()

    db.refresh(org); db.refresh(admin); db.refresh(candidate)
    db.refresh(job); db.refresh(session); db.refresh(qset)
    db.refresh(q1); db.refresh(q2)

    return {
        "org": org,
        "admin": admin,
        "candidate": candidate,
        "job": job,
        "session": session,
        "qset": qset,
        "q1": q1,
        "q2": q2,
    }


@pytest.fixture
def candidate_token(seed: dict) -> str:
    return create_access_token({
        "sub": str(seed["candidate"].id),
        "role": "candidate",
        "org_id": str(seed["org"].id),
        "assessment_session_id": str(seed["session"].id),
    })


@pytest.fixture
def user_token(seed: dict) -> str:
    return create_access_token({
        "sub": str(seed["admin"].id),
        "role": "admin",
        "org_id": str(seed["org"].id),
    })


@pytest_asyncio.fixture
async def async_client(db: Session):
    from src.main import app
    from src.database import get_db
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

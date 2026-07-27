import os
import uuid as _uuid
from unittest.mock import patch

import fakeredis
import pytest
import pytest_asyncio
import src.models  # noqa: F401
from httpx import ASGITransport, AsyncClient
from passlib.context import CryptContext
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from src.models.assessment_sessions import AssessmentSession
from src.models.base import Base
from src.models.candidate_profiles import CandidateProfile
from src.models.candidates import Candidate
from src.models.job_assessments import JobAssessment
from src.models.orgs import Org
from src.models.users import User
from src.modules.auth.token import create_access_token

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://arap:arap@localhost:5434/arap_test",
)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Fake agent output — 2 questions, first has resume_reference=True
FAKE_QUESTIONS = [
    {
        "question": "Describe your async Python experience at Acme Corp.",
        "category": "Technical",
        "target_competencies": ["Technical Accuracy"],
        "difficulty": "hard",
        "answer_format": "long_text",
        "resume_reference": True,
    },
    {
        "question": "Tell me about a conflict you resolved in your team.",
        "category": "Conflict Resolution",
        "target_competencies": ["Conflict Handling"],
        "difficulty": "medium",
        "answer_format": "long_text",
        "resume_reference": False,
    },
]

# Fake embedding: use distinct fixed vectors (dim=1536)
FAKE_EMBEDDINGS = [
    [0.01 * i for i in range(1536)],   # question 0
    [-0.01 * i for i in range(1536)],  # question 1 — dissimilar to q0
]


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
    uid = _uuid.uuid4().hex[:8]
    org = Org(name=f"QS Test Org {uid}")
    db.add(org)
    db.flush()

    admin = User(
        org_id=org.id, email=f"admin-{uid}@qs.com", role="admin",
        password_hash=pwd_context.hash("pw"),
    )
    db.add(admin)
    db.flush()

    candidate = Candidate(
        org_id=org.id, name="Jane Doe", email=f"jane-{uid}@example.com",
        auth_method="magic_link",
    )
    db.add(candidate)
    db.flush()

    job = JobAssessment(
        org_id=org.id,
        title="Senior Backend Engineer",
        department="Engineering",
        difficulty_level="senior",
        duration_minutes=60,
        required_skills=["Python"],
        preferred_skills=["Docker"],
        behavioral_competencies=["problem_solving"],
        leadership_competencies=["mentoring"],
        competency_weightage={"problem_solving": 70.0, "mentoring": 30.0},
        created_by=admin.id,
        job_profile={
            "normalized_title": "Senior Backend Engineer",
            "role_summary": "Build scalable APIs.",
            "key_responsibilities": ["Design REST APIs"],
            "required_skills": ["Python"],
            "preferred_skills": ["Docker"],
            "difficulty_level": "senior",
        },
    )
    db.add(job)
    db.flush()

    profile = CandidateProfile(
        org_id=org.id,
        candidate_id=candidate.id,
        job_assessment_id=job.id,
        skill_matrix={"aligned": [{"skill": "Python", "alignment": "yes"}], "raw": {}},
        experience_matrix={"employment_history": [], "career_timeline": {}, "career_velocity": "Promoted twice"},
        leadership_level_estimate="Manager",
        strengths=["Deep Python expertise"],
        risk_flags=["No direct people-management despite Manager title at Acme Corp"],
        parsing_confidence=0.85,
    )
    db.add(profile)
    db.flush()

    session = AssessmentSession(
        org_id=org.id,
        job_assessment_id=job.id,
        candidate_id=candidate.id,
        candidate_profile_id=profile.id,
        time_budget_seconds=3600,
    )
    db.add(session)
    db.commit()

    db.refresh(org); db.refresh(admin); db.refresh(candidate)
    db.refresh(job); db.refresh(profile); db.refresh(session)

    return {
        "org": org, "admin": admin, "candidate": candidate,
        "job": job, "profile": profile, "session": session,
    }


@pytest.fixture
def user_token(seed):
    return create_access_token({
        "sub": str(seed["admin"].id),
        "role": "admin",
        "org_id": str(seed["org"].id),
    })


@pytest.fixture
def mock_agent():
    with patch(
        "src.modules.question_sets.service.run_question_generation_agent",
        return_value=FAKE_QUESTIONS,
    ) as m:
        yield m


@pytest.fixture
def mock_embed():
    with patch(
        "src.modules.question_sets.service.embed_texts",
        return_value=FAKE_EMBEDDINGS,
    ) as m:
        yield m


@pytest_asyncio.fixture
async def async_client(db, r):
    from src.database import get_db, get_redis
    from src.main import app
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: r
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

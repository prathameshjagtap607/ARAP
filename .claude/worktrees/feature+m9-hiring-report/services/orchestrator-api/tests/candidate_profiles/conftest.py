import os
import uuid as _uuid
from unittest.mock import patch

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
from src.models.candidates import Candidate
from src.models.job_assessments import JobAssessment
from src.models.candidate_profiles import CandidateProfile
from src.modules.auth.token import create_access_token

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://arap:arap@localhost:5434/arap_test",
)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

FAKE_AGENT_RESULT = {
    "summary": "Jane is a seasoned backend engineer with 8 years of Python expertise.",
    "skill_matrix_aligned": [
        {
            "skill": "Python",
            "source": "required",
            "alignment": "yes",
            "estimated_years": 8.0,
            "confidence": 0.95,
            "evidence": "8 years Python development across 3 companies",
        }
    ],
    "leadership": {
        "level": "Manager",
        "career_velocity": "Promoted twice in 4 years",
        "scope": {"team_size": 8, "budget": None, "geography": "Remote — APAC"},
    },
    "strengths": ["Deep Python expertise", "Cross-functional leadership"],
    "risk_flags": ["No direct people-management despite Manager title at Acme Corp"],
}


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
    org = Org(name="CP Test Org")
    db.add(org)
    db.flush()

    _uid = _uuid.uuid4().hex[:8]
    admin = User(
        org_id=org.id, email=f"admin-{_uid}@cp.com", role="admin",
        password_hash=pwd_context.hash("pw"),
    )
    db.add(admin)
    db.flush()

    candidate = Candidate(
        org_id=org.id, name="Jane Doe", email=f"jane-{_uid}@example.com",
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
        required_skills=["Python", "FastAPI"],
        preferred_skills=["Docker"],
        behavioral_competencies=["problem_solving"],
        leadership_competencies=["mentoring"],
        competency_weightage={"problem_solving": 60.0, "mentoring": 40.0},
        created_by=admin.id,
        job_profile={
            "normalized_title": "Senior Backend Engineer",
            "role_summary": "Build scalable APIs.",
            "key_responsibilities": ["Design REST APIs"],
            "required_skills": ["Python", "FastAPI"],
            "preferred_skills": ["Docker"],
            "difficulty_level": "senior",
            "generated_at": "2026-07-24T00:00:00",
        },
    )
    db.add(job)
    db.flush()

    profile = CandidateProfile(
        org_id=org.id,
        candidate_id=candidate.id,
        job_assessment_id=job.id,
        skill_matrix={
            "explicit": ["Python", "FastAPI"],
            "inferred": ["REST APIs"],
            "tech_used": ["PostgreSQL"],
        },
        experience_matrix={
            "employment_history": [
                {
                    "company": "Acme Corp",
                    "title": "Engineering Manager",
                    "start": "2020-01",
                    "end": None,
                    "team_size": 8,
                    "scope": "Backend platform",
                    "key_achievements": ["Reduced latency by 40%"],
                }
            ],
            "career_timeline": {"total_years": 8, "job_count": 3, "gaps": []},
        },
        leadership_level_estimate="Manager",
        strengths=[],
        risk_flags=[],
        parsing_confidence=0.85,
        field_confidence={"skills": 0.9, "employment_history": 0.85},
    )
    db.add(profile)
    db.commit()
    db.refresh(org); db.refresh(admin); db.refresh(candidate)
    db.refresh(job); db.refresh(profile)

    return {
        "org": org,
        "admin": admin,
        "candidate": candidate,
        "job": job,
        "profile": profile,
    }


@pytest.fixture
def user_token(seed):
    return create_access_token({
        "sub": str(seed["admin"].id),
        "role": "admin",
        "org_id": str(seed["org"].id),
    })


@pytest.fixture
def mock_cp_agent():
    with patch(
        "src.modules.candidate_profiles.service.run_candidate_profile_agent"
    ) as m:
        m.return_value = FAKE_AGENT_RESULT
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

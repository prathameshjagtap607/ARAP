from unittest.mock import patch

import pytest
import src.models  # noqa: F401
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.models.base import Base
from src.models.job_assessments import JobAssessment
from src.models.orgs import Org
from src.models.users import User

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


def test_agent_writes_job_profile(db, assessment):
    from agents.job_description.agent import run_job_description_agent

    with patch("agents.job_description.agent.call_tool", return_value=dict(_FAKE_PROFILE)):
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

    with patch("agents.job_description.agent.call_tool", side_effect=Exception("API down")):
        run_job_description_agent(db, assessment)

    db.refresh(assessment)
    assert assessment.job_profile is None

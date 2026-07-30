import os
import uuid as _uuid
from datetime import UTC, datetime

import pytest
import src.models  # noqa: F401
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from src.models.assessment_sessions import AssessmentSession
from src.models.base import Base
from src.models.candidates import Candidate
from src.models.hiring_reports import HiringReport
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
def analytics_seed(db: Session) -> dict:
    uid = _uuid.uuid4().hex[:8]
    org = Org(name=f"Analytics Test Org {uid}")
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

    job = JobAssessment(
        org_id=org.id,
        title="Software Engineer",
        department="Engineering",
        difficulty_level="mid",
        duration_minutes=45,
        competency_weightage={"problem_solving": 50.0, "communication": 50.0},
        created_by=admin.id,
    )
    db.add(job)
    db.flush()

    sessions = []
    reports = []
    for i in range(3):
        candidate = Candidate(
            org_id=org.id,
            name=f"Candidate {uid}-{i}",
            email=f"cand-{uid}-{i}@example.com",
            auth_method="magic_link",
        )
        db.add(candidate)
        db.flush()

        sess = AssessmentSession(
            org_id=org.id,
            job_assessment_id=job.id,
            candidate_id=candidate.id,
            time_budget_seconds=2700,
            status="completed",
            invited_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        db.add(sess)
        db.flush()

        score = 3.0 + i * 0.5
        verdict = "hire" if score >= 3.5 else "consider"
        report = HiringReport(
            org_id=org.id,
            session_id=sess.id,
            score_rollup={
                "overall": score,
                "composite_scores": {
                    "problem_solving": score + 0.1,
                    "communication": score - 0.1,
                },
            },
            verdict=verdict,
        )
        db.add(report)
        db.flush()

        sessions.append(sess)
        reports.append(report)

    db.commit()
    return {
        "org": org,
        "admin": admin,
        "job": job,
        "sessions": sessions,
        "reports": reports,
    }


@pytest.fixture
def user_token(analytics_seed: dict) -> str:
    return create_access_token({
        "sub": str(analytics_seed["admin"].id),
        "role": "admin",
        "org_id": str(analytics_seed["org"].id),
    })

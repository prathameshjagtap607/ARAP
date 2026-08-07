import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from src.database import get_db
from src.models import Base, Candidate, JobAssessment, Org

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

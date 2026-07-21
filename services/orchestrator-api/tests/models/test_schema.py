import uuid
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from src.models.orgs import Org
from src.models.users import User
from src.models.job_assessments import JobAssessment
from src.models.competency_library import CompetencyLibrary


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


# ── JobAssessment ─────────────────────────────────────────────────────────────

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


# ── CompetencyLibrary ─────────────────────────────────────────────────────────

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

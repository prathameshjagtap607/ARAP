import uuid
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from src.models.orgs import Org
from src.models.users import User
from src.models.job_assessments import JobAssessment
from src.models.competency_library import CompetencyLibrary
from src.models.candidates import Candidate
from src.models.clients import Client
from src.models.candidate_profiles import CandidateProfile
from src.models.assessment_sessions import AssessmentSession
from src.models.question_sets import QuestionSet
from src.models.session_questions import SessionQuestion


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


# ── Candidate ─────────────────────────────────────────────────────────────────

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


# ── Client ────────────────────────────────────────────────────────────────────

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


# ── CandidateProfile ──────────────────────────────────────────────────────────

def test_candidate_profiles_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("candidate_profiles")}
    expected = {
        "id", "org_id", "candidate_id", "job_assessment_id",
        "summary", "skill_matrix", "experience_matrix",
        "leadership_level_estimate", "strengths", "risk_flags",
        "parsing_confidence", "created_at",
    }
    assert cols == expected


# ── AssessmentSession ─────────────────────────────────────────────────────────

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


# ── QuestionSet ───────────────────────────────────────────────────────────────

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


# ── SessionQuestion ───────────────────────────────────────────────────────────

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

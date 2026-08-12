import uuid

from sqlalchemy.orm import Session

from agents.job_description.agent import run_job_description_agent
from src.models.assessment_sessions import AssessmentSession
from src.models.candidate_profiles import CandidateProfile
from src.models.candidates import Candidate
from src.models.job_assessments import JobAssessment
from src.modules.job_assessments.schemas import (
    InviteRequest,
    InviteResponse,
    JobAssessmentCreate,
    JobAssessmentUpdate,
)


def list_assessments(
    db: Session,
    org_id: uuid.UUID,
    is_template: bool | None = None,
    user_id: uuid.UUID | None = None,
    role: str | None = None,
    filter_user_id: uuid.UUID | None = None,
) -> list[JobAssessment]:
    q = db.query(JobAssessment).filter_by(org_id=org_id)
    if is_template is not None:
        q = q.filter(JobAssessment.is_template == is_template)
    if role == "user" and user_id is not None:
        q = q.filter(JobAssessment.created_by == user_id)
    elif role == "admin" and filter_user_id is not None:
        q = q.filter(JobAssessment.created_by == filter_user_id)
    return q.all()


def get_assessment(db: Session, org_id: uuid.UUID, assessment_id: uuid.UUID) -> JobAssessment:
    row = db.query(JobAssessment).filter_by(id=assessment_id, org_id=org_id).first()
    if row is None:
        raise LookupError("Job assessment not found")
    return row


def create_assessment(
    db: Session, org_id: uuid.UUID, user_id: uuid.UUID, data: JobAssessmentCreate
) -> JobAssessment:
    row = JobAssessment(
        org_id=org_id,
        title=data.title,
        department=data.department,
        experience_min=data.experience_min,
        experience_max=data.experience_max,
        required_skills=data.required_skills,
        preferred_skills=data.preferred_skills,
        responsibilities=data.responsibilities,
        education=data.education,
        certifications=data.certifications,
        behavioral_competencies=data.behavioral_competencies,
        leadership_competencies=data.leadership_competencies,
        culture_values=data.culture_values,
        difficulty_level=data.difficulty_level,
        duration_minutes=data.duration_minutes,
        competency_weightage=data.competency_weightage,
        is_template=data.is_template,
        role_family=data.role_family,
        created_by=user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    run_job_description_agent(db, row)
    db.refresh(row)
    return row


def update_assessment(
    db: Session, org_id: uuid.UUID, assessment_id: uuid.UUID, data: JobAssessmentUpdate
) -> JobAssessment:
    row = get_assessment(db, org_id, assessment_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    run_job_description_agent(db, row)
    db.refresh(row)
    return row


def delete_assessment(db: Session, org_id: uuid.UUID, assessment_id: uuid.UUID) -> None:
    row = get_assessment(db, org_id, assessment_id)
    has_sessions = db.query(AssessmentSession).filter_by(
        job_assessment_id=assessment_id
    ).first() is not None
    if has_sessions:
        raise PermissionError("Cannot delete assessment with existing sessions")
    has_candidate_profiles = db.query(CandidateProfile).filter_by(
        job_assessment_id=assessment_id
    ).first() is not None
    if has_candidate_profiles:
        raise PermissionError("Cannot delete assessment with existing candidate profiles")
    db.delete(row)
    db.commit()


def invite_candidate(
    db: Session, org_id: uuid.UUID, assessment_id: uuid.UUID,
    user_id: uuid.UUID, data: InviteRequest,
) -> InviteResponse:
    """Register a candidate + session for this job assessment.

    Does NOT send the test-link email — per PRD §8, the email is only sent
    once a resume has been ingested and the question set is locked
    (see sessions.service.invite_candidate / POST /sessions/{id}/invite).
    """
    get_assessment(db, org_id, assessment_id)

    from sqlalchemy.exc import IntegrityError

    candidate = db.query(Candidate).filter_by(
        org_id=org_id, email=data.candidate_email
    ).first()
    if candidate is None:
        try:
            candidate = Candidate(
                org_id=org_id,
                name=data.candidate_name,
                email=data.candidate_email,
                auth_method="magic_link",
            )
            db.add(candidate)
            db.flush()
        except IntegrityError:
            db.rollback()
            candidate = db.query(Candidate).filter_by(
                org_id=org_id, email=data.candidate_email
            ).first()
    elif candidate.name != data.candidate_name:
        # A candidate record already exists for this email (e.g. invited to
        # a different assessment before) — keep the name in sync with what
        # was actually typed on this invite, instead of silently freezing
        # it to whatever was entered the first time.
        candidate.name = data.candidate_name
        db.flush()

    from sqlalchemy import text as _text

    active_template = db.execute(
        _text("""
            SELECT id FROM prompt_templates
            WHERE agent_name = 'question_generator'
              AND is_active = true
              AND (org_id = :org_id OR org_id IS NULL)
            ORDER BY org_id NULLS LAST
            LIMIT 1
        """),
        {"org_id": org_id},
    ).scalar()

    session = AssessmentSession(
        org_id=org_id,
        job_assessment_id=assessment_id,
        candidate_id=candidate.id,
        time_budget_seconds=data.time_budget_seconds,
        prompt_template_id=active_template,
        invited_by=user_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return InviteResponse(
        link="",
        email_sent=False,
        session_id=str(session.id),
        candidate_id=str(candidate.id),
    )

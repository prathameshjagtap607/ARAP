import uuid

from sqlalchemy.orm import Session

from agents.job_description.agent import run_job_description_agent
from src.models.assessment_sessions import AssessmentSession
from src.models.candidates import Candidate
from src.models.job_assessments import JobAssessment
from src.modules.job_assessments.schemas import (
    CloneRequest,
    InviteRequest,
    InviteResponse,
    JobAssessmentCreate,
    JobAssessmentUpdate,
)


def list_assessments(
    db: Session, org_id: uuid.UUID, is_template: bool | None = None
) -> list[JobAssessment]:
    q = db.query(JobAssessment).filter_by(org_id=org_id)
    if is_template is not None:
        q = q.filter(JobAssessment.is_template == is_template)
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
    db.delete(row)
    db.commit()


def clone_assessment(
    db: Session, org_id: uuid.UUID, user_id: uuid.UUID,
    assessment_id: uuid.UUID, overrides: CloneRequest,
) -> JobAssessment:
    source = get_assessment(db, org_id, assessment_id)
    clone = JobAssessment(
        org_id=org_id,
        title=source.title,
        department=source.department,
        experience_min=source.experience_min,
        experience_max=source.experience_max,
        required_skills=overrides.required_skills if overrides.required_skills is not None else list(source.required_skills),
        preferred_skills=overrides.preferred_skills if overrides.preferred_skills is not None else list(source.preferred_skills),
        responsibilities=source.responsibilities,
        education=source.education,
        certifications=list(source.certifications),
        behavioral_competencies=list(source.behavioral_competencies),
        leadership_competencies=list(source.leadership_competencies),
        culture_values=list(source.culture_values),
        difficulty_level=source.difficulty_level,
        duration_minutes=source.duration_minutes,
        competency_weightage=overrides.competency_weightage if overrides.competency_weightage is not None else dict(source.competency_weightage),
        is_template=False,
        role_family=overrides.role_family if overrides.role_family is not None else source.role_family,
        created_by=user_id,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    run_job_description_agent(db, clone)
    db.refresh(clone)
    return clone


def invite_candidate(
    db: Session, org_id: uuid.UUID, assessment_id: uuid.UUID,
    user_id: uuid.UUID, data: InviteRequest,
) -> InviteResponse:
    assessment = get_assessment(db, org_id, assessment_id)

    from sqlalchemy.exc import IntegrityError
    from src.modules.sessions.email import send_invite_email

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

    session = AssessmentSession(
        org_id=org_id,
        job_assessment_id=assessment_id,
        candidate_id=candidate.id,
        time_budget_seconds=data.time_budget_seconds,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Generate real magic-link token for candidate
    from src.modules.auth.token import generate_login_token, hash_login_token
    from datetime import timedelta
    from src.database import UTC
    from datetime import datetime

    raw_token = generate_login_token()
    candidate.login_token_hash = hash_login_token(raw_token)
    candidate.login_token_expires_at = datetime.now(UTC) + timedelta(minutes=15)
    db.add(candidate)
    db.commit()

    # Generate invite link with real magic-link token
    link = f"http://localhost:3000/assessment/{session.id}?token={raw_token}"
    email_sent = send_invite_email(
        to=candidate.email,
        link=link,
        job_title=assessment.title,
        duration_minutes=assessment.duration_minutes,
    )

    return InviteResponse(
        link=link,
        email_sent=email_sent,
    )

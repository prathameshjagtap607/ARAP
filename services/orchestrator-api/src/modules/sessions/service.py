import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.config import settings
from src.models.assessment_sessions import AssessmentSession
from src.models.candidates import Candidate
from src.models.job_assessments import JobAssessment
from src.models.question_sets import QuestionSet
from src.models.session_questions import SessionQuestion
from src.modules.auth import service as auth_service
from src.modules.sessions.email import send_invite_email
from src.modules.sessions.schemas import (
    AnswerResponse,
    InviteResponse,
    QuestionInSession,
    SessionStateResponse,
    SubmitResponse,
)

logger = logging.getLogger(__name__)


def _get_session_or_404(db: Session, session_id: uuid.UUID, org_id: uuid.UUID) -> AssessmentSession:
    s = db.query(AssessmentSession).filter_by(id=session_id, org_id=org_id).first()
    if not s:
        raise LookupError("assessment session not found")
    return s


def _seconds_remaining(session: AssessmentSession) -> int | None:
    if session.started_at is None:
        return None
    started = session.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    elapsed = int((datetime.now(UTC) - started).total_seconds())
    return max(0, session.time_budget_seconds - elapsed)


def _build_state(db: Session, session: AssessmentSession) -> SessionStateResponse:
    job = db.query(JobAssessment).filter_by(id=session.job_assessment_id).first()
    qset = db.query(QuestionSet).filter_by(session_id=session.id).first()
    questions: list[QuestionInSession] = []
    if qset:
        rows = (
            db.query(SessionQuestion)
            .filter_by(question_set_id=qset.id)
            .order_by(SessionQuestion.sequence_no)
            .all()
        )
        questions = [QuestionInSession.model_validate(r) for r in rows]
    return SessionStateResponse(
        id=session.id,
        status=session.status,
        seconds_remaining=_seconds_remaining(session),
        time_budget_seconds=session.time_budget_seconds,
        job_title=job.title if job else "",
        duration_minutes=job.duration_minutes if job else 0,
        questions=questions,
    )


def invite_candidate(
    db: Session, session_id: uuid.UUID, org_id: uuid.UUID
) -> InviteResponse:
    session = _get_session_or_404(db, session_id, org_id)
    qset = db.query(QuestionSet).filter_by(session_id=session_id).first()
    if not qset or qset.locked_at is None:
        raise ValueError("question set must be locked before sending invite")

    candidate = db.query(Candidate).filter_by(id=session.candidate_id, org_id=org_id).first()
    job = db.query(JobAssessment).filter_by(id=session.job_assessment_id).first()

    raw_token = auth_service.request_candidate_token(
        db, candidate.email, org_id, session_id
    )
    link = f"{settings.CANDIDATE_PORTAL_URL}/assessment/{session_id}?token={raw_token}"

    email_sent = send_invite_email(
        to=candidate.email,
        link=link,
        job_title=job.title if job else "",
        duration_minutes=job.duration_minutes if job else 0,
    )
    logger.info("invite sent session=%s email_sent=%s", session_id, email_sent)
    return InviteResponse(link=link, email_sent=email_sent)


def get_session_state(
    db: Session, session_id: uuid.UUID, org_id: uuid.UUID
) -> SessionStateResponse:
    session = _get_session_or_404(db, session_id, org_id)
    return _build_state(db, session)


def start_session(
    db: Session, session_id: uuid.UUID, org_id: uuid.UUID
) -> SessionStateResponse:
    session = _get_session_or_404(db, session_id, org_id)
    if session.status in ("completed", "expired"):
        raise ValueError(f"session is already {session.status}")
    if session.status == "invited":
        session.started_at = datetime.now(UTC)
        session.status = "in_progress"
        db.flush()
        db.commit()
    return _build_state(db, session)

import logging
import uuid
from collections.abc import Callable
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
    AdaptiveAnswerResponse,
    AnswerResponse,
    InviteResponse,
    QuestionInSession,
    RankingAnswerResponse,
    ReflectionAnswerResponse,
    SessionStateResponse,
    SubmitResponse,
)

logger = logging.getLogger(__name__)


def _get_session_or_404(db: Session, session_id: uuid.UUID, org_id: uuid.UUID) -> AssessmentSession:
    s = db.query(AssessmentSession).filter_by(id=session_id, org_id=org_id).first()
    if not s:
        raise LookupError("assessment session not found")
    return s


def delete_session(db: Session, session_id: uuid.UUID, org_id: uuid.UUID) -> None:
    from src.models.answer_corpus import AnswerCorpus
    from src.models.behavior_profiles import BehaviorProfile
    from src.models.candidate_profiles import CandidateProfile
    from src.models.hiring_reports import HiringReport
    from src.models.integrity_flags import IntegrityFlag
    from src.models.report_shares import ReportShare

    session = _get_session_or_404(db, session_id, org_id)

    report_ids = [
        r.id for r in db.query(HiringReport.id).filter_by(session_id=session_id).all()
    ]
    if report_ids:
        db.query(ReportShare).filter(
            ReportShare.hiring_report_id.in_(report_ids)
        ).delete(synchronize_session="fetch")

    db.query(HiringReport).filter_by(session_id=session_id).delete(synchronize_session="fetch")
    db.query(IntegrityFlag).filter_by(session_id=session_id).delete(synchronize_session="fetch")
    db.query(AnswerCorpus).filter_by(session_id=session_id).delete(synchronize_session="fetch")
    db.query(BehaviorProfile).filter_by(session_id=session_id).delete(synchronize_session="fetch")
    db.flush()

    qset = db.query(QuestionSet).filter_by(session_id=session_id).first()
    if qset:
        db.query(SessionQuestion).filter_by(question_set_id=qset.id).delete(synchronize_session="fetch")
        db.flush()
        db.query(QuestionSet).filter_by(id=qset.id).delete(synchronize_session="fetch")
        db.flush()

    candidate_id = session.candidate_id
    job_assessment_id = session.job_assessment_id
    db.delete(session)
    db.flush()

    other_session_exists = db.query(AssessmentSession).filter_by(
        candidate_id=candidate_id, job_assessment_id=job_assessment_id
    ).first() is not None
    if not other_session_exists:
        db.query(CandidateProfile).filter_by(
            candidate_id=candidate_id, job_assessment_id=job_assessment_id
        ).delete(synchronize_session="fetch")
    db.commit()


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
    if not candidate:
        raise LookupError("candidate not found for this session")
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


def save_answer(
    db: Session,
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    org_id: uuid.UUID,
    answer_text: str,
) -> AnswerResponse:
    session = _get_session_or_404(db, session_id, org_id)
    if session.status != "in_progress":
        raise ValueError(f"session is {session.status} — answers not accepted")
    q = (
        db.query(SessionQuestion)
        .join(QuestionSet, SessionQuestion.question_set_id == QuestionSet.id)
        .filter(
            SessionQuestion.id == question_id,
            QuestionSet.session_id == session_id,
        )
        .first()
    )
    if not q:
        raise LookupError("question not found")
    q.answer_text = answer_text
    q.answered_at = datetime.now(UTC)
    db.flush()
    db.commit()
    db.refresh(q)
    return AnswerResponse.model_validate(q)


def save_adaptive_answer(
    db: Session,
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    org_id: uuid.UUID,
    adaptive_answer_text: str,
) -> AdaptiveAnswerResponse:
    """DISC-Based Generative Leadership Question Framework — Natural vs
    Adaptive Behaviour mechanic (spec §8): captures the candidate's ADAPTIVE
    response ("what would be most effective, even if not your natural
    choice?") separately from their natural answer_text/answered_at, without
    touching the natural-answer flow at all."""
    session = _get_session_or_404(db, session_id, org_id)
    if session.status != "in_progress":
        raise ValueError(f"session is {session.status} — answers not accepted")
    q = (
        db.query(SessionQuestion)
        .join(QuestionSet, SessionQuestion.question_set_id == QuestionSet.id)
        .filter(
            SessionQuestion.id == question_id,
            QuestionSet.session_id == session_id,
        )
        .first()
    )
    if not q:
        raise LookupError("question not found")
    q.adaptive_answer_text = adaptive_answer_text
    q.adaptive_answered_at = datetime.now(UTC)
    db.flush()
    db.commit()
    db.refresh(q)
    return AdaptiveAnswerResponse.model_validate(q)


def save_ranking_answer(
    db: Session,
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    org_id: uuid.UUID,
    ranking_order: list[str],
) -> RankingAnswerResponse:
    """DISC-Based Generative Leadership Question Framework — Question
    Formats (spec §7), 'Ranking' format: captures the candidate's ordering
    of the 4 options from most-to-least-likely, as an ADDITIONAL signal
    alongside their single natural answer_text pick — never replaces or
    gates the natural-answer flow, which still drives DISC scoring for
    every question regardless of format."""
    session = _get_session_or_404(db, session_id, org_id)
    if session.status != "in_progress":
        raise ValueError(f"session is {session.status} — answers not accepted")
    q = (
        db.query(SessionQuestion)
        .join(QuestionSet, SessionQuestion.question_set_id == QuestionSet.id)
        .filter(
            SessionQuestion.id == question_id,
            QuestionSet.session_id == session_id,
        )
        .first()
    )
    if not q:
        raise LookupError("question not found")
    q.ranking_order = ranking_order
    q.ranking_answered_at = datetime.now(UTC)
    db.flush()
    db.commit()
    db.refresh(q)
    return RankingAnswerResponse.model_validate(q)


def save_reflection_answer(
    db: Session,
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    org_id: uuid.UUID,
    reflection_text: str,
) -> ReflectionAnswerResponse:
    """DISC-Based Generative Leadership Question Framework — Question
    Formats (spec §7), 'Reflection' format: captures the candidate's
    free-text self-reflection as an ADDITIONAL signal alongside their
    single natural answer_text pick — never replaces or gates the
    natural-answer flow."""
    session = _get_session_or_404(db, session_id, org_id)
    if session.status != "in_progress":
        raise ValueError(f"session is {session.status} — answers not accepted")
    q = (
        db.query(SessionQuestion)
        .join(QuestionSet, SessionQuestion.question_set_id == QuestionSet.id)
        .filter(
            SessionQuestion.id == question_id,
            QuestionSet.session_id == session_id,
        )
        .first()
    )
    if not q:
        raise LookupError("question not found")
    q.reflection_text = reflection_text
    q.reflection_answered_at = datetime.now(UTC)
    db.flush()
    db.commit()
    db.refresh(q)
    return ReflectionAnswerResponse.model_validate(q)


def submit_session(
    db: Session,
    session_id: uuid.UUID,
    org_id: uuid.UUID,
    on_complete: Callable | None = None,
) -> SubmitResponse:
    session = _get_session_or_404(db, session_id, org_id)
    if session.status == "in_progress":
        pass  # continue to submit logic below
    elif session.status in ("completed", "expired"):
        return SubmitResponse(status=session.status, completed_at=session.completed_at)
    else:
        raise ValueError(f"session must be in_progress to submit (is {session.status})")

    now = datetime.now(UTC)
    has_answers = (
        db.query(SessionQuestion)
        .join(QuestionSet, SessionQuestion.question_set_id == QuestionSet.id)
        .filter(QuestionSet.session_id == session_id, SessionQuestion.answered_at.isnot(None))
        .count()
    ) > 0

    expired = _seconds_remaining(session) == 0

    if expired and not has_answers:
        session.status = "expired"
    else:
        session.status = "completed"
        session.completed_at = now

    db.flush()
    db.commit()
    logger.info("session %s submitted status=%s", session_id, session.status)

    if session.status == "completed" and on_complete is not None:
        on_complete()

    return SubmitResponse(status=session.status, completed_at=session.completed_at)


def calibrate_answer(
    db: Session,
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    org_id: uuid.UUID,
    override_score: int,
    comment: str,
    reviewer_id: str,
) -> dict:
    from src.models.hiring_reports import HiringReport

    _get_session_or_404(db, session_id, org_id)

    q = (
        db.query(SessionQuestion)
        .join(QuestionSet, SessionQuestion.question_set_id == QuestionSet.id)
        .filter(
            SessionQuestion.id == question_id,
            QuestionSet.session_id == session_id,
        )
        .first()
    )
    if not q:
        raise LookupError("question not found")

    calibration = {
        "override_score": override_score,
        "comment": comment,
        "overridden_by": str(reviewer_id),
        "overridden_at": datetime.now(UTC).isoformat(),
    }
    current_eval = dict(q.evaluation) if q.evaluation else {}
    current_eval["calibration"] = calibration
    q.evaluation = current_eval
    db.flush()

    report = db.query(HiringReport).filter_by(session_id=session_id).first()
    if report:
        overrides = list(report.reviewer_override or [])
        overrides.append({"question_id": str(question_id), **calibration})
        report.reviewer_override = overrides
    else:
        logger.warning(
            "calibrate_answer: no hiring report found for session %s — reviewer_override not recorded",
            session_id,
        )

    db.commit()
    return calibration


def list_sessions(
    db: Session,
    org_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    role: str | None = None,
    filter_user_id: uuid.UUID | None = None,
) -> list:
    from sqlalchemy import func as _func

    from src.modules.sessions.schemas import SessionListItem

    query = (
        db.query(
            AssessmentSession.id,
            AssessmentSession.candidate_id,
            AssessmentSession.job_assessment_id,
            _func.coalesce(AssessmentSession.candidate_name, Candidate.name).label("candidate_name"),
            Candidate.email.label("candidate_email"),
            JobAssessment.title.label("job_title"),
            AssessmentSession.status,
            AssessmentSession.invited_at.label("created_at"),
            AssessmentSession.started_at,
            AssessmentSession.completed_at.label("submitted_at"),
        )
        .join(Candidate, AssessmentSession.candidate_id == Candidate.id)
        .join(JobAssessment, AssessmentSession.job_assessment_id == JobAssessment.id)
        .filter(AssessmentSession.org_id == org_id)
    )
    if role == "user" and user_id is not None:
        query = query.filter(AssessmentSession.invited_by == user_id)
    elif role == "admin" and filter_user_id is not None:
        query = query.filter(AssessmentSession.invited_by == filter_user_id)

    sessions = query.order_by(AssessmentSession.invited_at.desc()).all()

    return [SessionListItem(**dict(s._mapping)) for s in sessions]

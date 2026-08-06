import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from src.database import get_redis
from src.models.assessment_sessions import AssessmentSession
from src.models.candidates import Candidate
from src.models.clients import Client
from src.models.hiring_reports import HiringReport
from src.models.job_assessments import JobAssessment
from src.models.report_shares import ReportShare
from src.modules.analytics.cache import invalidate_org_analytics
from src.modules.reports.schemas import (
    FullReportResponse,
    ReportListItem,
    ReportListResponse,
    ReportResponse,
    ReviewerFeedbackRequest,
    ReviewerFeedbackResponse,
    SharedReportResponse,
    ShareLinkRequest,
    ShareLinkResponse,
)


def _load_session_and_report(
    db: Session, session_id: uuid.UUID, org_id: uuid.UUID
) -> tuple[AssessmentSession, HiringReport]:
    """Return (session, report) or raise LookupError / PermissionError."""
    session = db.query(AssessmentSession).filter_by(id=session_id).first()
    if not session:
        raise LookupError("assessment session not found")
    if session.org_id != org_id:
        raise PermissionError("session does not belong to this org")
    report = db.query(HiringReport).filter_by(session_id=session_id).first()
    if not report or report.full_report == {}:
        raise LookupError("full report not available")
    return session, report


def get_full_report(
    db: Session, session_id: uuid.UUID, org_id: uuid.UUID
) -> FullReportResponse:
    _session, report = _load_session_and_report(db, session_id, org_id)
    integrity_review = bool((report.integrity_summary or {}).get("human_review_required", False))
    confidence_review = bool((report.full_report or {}).get("meta", {}).get("requires_human_review", False))
    requires_human_review = integrity_review or confidence_review
    return FullReportResponse(
        session_id=session_id,
        report_ready=True,
        requires_human_review=requires_human_review,
        verdict=report.verdict,
        ai_confidence_score=float(report.ai_confidence_score) if report.ai_confidence_score is not None else None,
        salary_band=report.salary_band,
        full_report=report.full_report,
        reviewer_override=report.reviewer_override,
        created_at=report.created_at,
    )


def get_pdf_bytes(
    db: Session,
    session_id: uuid.UUID,
    org_id: uuid.UUID,
) -> bytes:
    from agents.report_generator.pdf import render_pdf

    session, report = _load_session_and_report(db, session_id, org_id)

    candidate = db.query(Candidate).filter_by(id=session.candidate_id).first()
    candidate_name = candidate.name if candidate else "Unknown"

    job = db.query(JobAssessment).filter_by(id=session.job_assessment_id).first()
    job_title = job.title if job else "Unknown"

    report_data = dict(report.full_report or {})
    report_data.setdefault("verdict", report.verdict)
    report_data.setdefault("ai_confidence_score", float(report.ai_confidence_score) if report.ai_confidence_score is not None else None)
    report_data.setdefault("executive_summary", report.executive_summary)

    if "meta" not in report_data or not report_data.get("executive_summary"):
        raise ValueError("Full report is not ready yet — narrative sections have not been generated")

    return render_pdf(
        report_data=report_data,
        candidate_name=candidate_name,
        job_title=job_title,
        include_transcript=False,
    )


def create_share_link(
    db: Session,
    session_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    body: ShareLinkRequest,
) -> ShareLinkResponse:
    session = db.query(AssessmentSession).filter_by(id=session_id, org_id=org_id).first()
    if not session:
        raise LookupError("assessment session not found")

    report = db.query(HiringReport).filter_by(session_id=session_id).first()
    if not report:
        raise LookupError("hiring report not found")

    client = db.query(Client).filter_by(id=body.client_id).first()
    if not client:
        raise LookupError("client not found")
    if client.org_id != org_id:
        raise PermissionError("client does not belong to this org")

    expires_at = datetime.now(UTC) + timedelta(days=body.expires_in_days)
    share = ReportShare(
        org_id=org_id,
        hiring_report_id=report.id,
        client_id=body.client_id,
        shared_by=user_id,
        expires_at=expires_at,
    )
    db.add(share)
    db.commit()
    db.refresh(share)

    return ShareLinkResponse(share_token=share.id, expires_at=share.expires_at)


def get_shared_report(db: Session, token: uuid.UUID) -> SharedReportResponse:
    share = db.query(ReportShare).filter_by(id=token).first()
    if not share:
        raise PermissionError("share link not found")
    now = datetime.now(UTC)
    if share.revoked_at is not None:
        raise PermissionError("share link has been revoked")
    if share.expires_at is not None and share.expires_at.replace(tzinfo=UTC) < now:
        raise PermissionError("share link has expired")

    report = db.query(HiringReport).filter_by(id=share.hiring_report_id).first()
    if not report:
        raise LookupError("hiring report not found")

    # Mask integrity details — only expose overall_risk + human_review_required
    full_report = dict(report.full_report or {})
    raw_integrity = report.integrity_summary or {}
    full_report["integrity_summary"] = {
        "overall_risk": raw_integrity.get("overall_risk"),
        "human_review_required": raw_integrity.get("human_review_required"),
    }

    integrity_review = bool(raw_integrity.get("human_review_required", False))
    confidence_review = bool((report.full_report or {}).get("meta", {}).get("requires_human_review", False))
    requires_human_review = integrity_review or confidence_review

    scoped_report = {
        k: v for k, v in full_report.items()
        if k not in ("strengths", "weaknesses", "salary_recommendation", "ai_confidence_score", "_recommendation_context")
    }
    return SharedReportResponse(
        session_id=report.session_id,
        verdict=report.verdict,
        executive_summary=(report.full_report or {}).get("executive_summary"),
        recommended_next_round=report.recommended_next_round,
        requires_human_review=requires_human_review,
        full_report=scoped_report,
    )


def submit_reviewer_feedback(
    db: Session,
    session_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    body: ReviewerFeedbackRequest,
) -> ReviewerFeedbackResponse:
    session = db.query(AssessmentSession).filter_by(id=session_id, org_id=org_id).first()
    if not session:
        raise LookupError("assessment session not found")

    report = db.query(HiringReport).filter_by(session_id=session_id).first()
    if not report:
        raise LookupError("hiring report not found")

    # discrepancy: hire/strong_hire vs no_hire
    hire_verdicts = {"hire", "strong_hire"}
    no_hire_verdicts = {"no_hire"}
    ai_verdict = (report.verdict or "").lower()
    decision = body.final_decision.lower()
    discrepancy_flag = (
        (ai_verdict in hire_verdicts and decision in no_hire_verdicts)
        or (ai_verdict in no_hire_verdicts and decision in hire_verdicts)
    )

    override = {
        "final_decision": body.final_decision,
        "comment": body.comment,
        "score_overrides": body.score_overrides,
        "submitted_at": datetime.now(UTC).isoformat(),
        "submitted_by": str(user_id),
        "discrepancy_flag": discrepancy_flag,
    }
    report.reviewer_override = override

    if body.score_overrides:
        rollup = dict(report.score_rollup or {})
        composite = dict(rollup.get("composite_scores") or {})
        for key, val in body.score_overrides.items():
            composite[key] = val
        rollup["composite_scores"] = composite
        report.score_rollup = rollup

    db.commit()
    try:
        invalidate_org_analytics(get_redis(), org_id)
    except Exception:
        pass  # cache invalidation is best-effort

    try:
        candidate = db.query(Candidate).filter_by(id=session.candidate_id).first()
        job = db.query(JobAssessment).filter_by(id=session.job_assessment_id).first()
        if candidate and job:
            from src.modules.sessions.email import send_decision_email
            send_decision_email(candidate.email, job.title, body.final_decision)
    except Exception:
        pass  # decision email is best-effort, never blocks the decision itself

    return ReviewerFeedbackResponse(reviewer_override=override)


def list_reports(
    db: Session,
    org_id: uuid.UUID,
    verdict: str | None = None,
    disc_category: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> ReportListResponse:
    query = (
        db.query(HiringReport, Candidate.name, JobAssessment.title)
        .join(AssessmentSession, HiringReport.session_id == AssessmentSession.id)
        .join(Candidate, AssessmentSession.candidate_id == Candidate.id)
        .join(JobAssessment, AssessmentSession.job_assessment_id == JobAssessment.id)
        .filter(HiringReport.org_id == org_id)
    )
    if verdict:
        query = query.filter(HiringReport.verdict == verdict)
    if disc_category:
        query = query.filter(
            HiringReport.full_report["disc_profile"]["primary"].astext == disc_category
        )
    if status == "awaiting_review":
        query = query.filter(HiringReport.reviewer_override.is_(None))
    if date_from:
        query = query.filter(HiringReport.created_at >= date_from)
    if date_to:
        query = query.filter(HiringReport.created_at <= date_to)

    total_count = query.count()
    rows = (
        query.order_by(HiringReport.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    items = [
        ReportListItem(
            id=report.id,
            session_id=report.session_id,
            candidate_name=candidate_name,
            job_title=job_title,
            verdict=report.verdict,
            overall_score=(report.score_rollup or {}).get("overall"),
            disc_primary=(report.full_report or {}).get("disc_profile", {}).get("primary")
            if report.full_report
            else None,
            disc_confidence=(report.full_report or {}).get("disc_profile", {}).get("confidence")
            if report.full_report
            else None,
            created_at=report.created_at,
        )
        for report, candidate_name, job_title in rows
    ]
    return ReportListResponse(items=items, total_count=total_count)


def get_report(db: Session, session_id: uuid.UUID, org_id: uuid.UUID) -> ReportResponse:
    session = db.query(AssessmentSession).filter_by(id=session_id, org_id=org_id).first()
    if not session:
        raise LookupError("assessment session not found")

    report = db.query(HiringReport).filter_by(session_id=session_id).first()
    if not report:
        return ReportResponse(
            session_id=session_id,
            report_ready=False,
            verdict=None,
            executive_summary=None,
            composite_scores=None,
            overall_score=None,
            suggested_hr_questions=[],
            recommended_next_round=None,
            training_needs=[],
            created_at=None,
        )

    rollup = report.score_rollup or {}
    return ReportResponse(
        session_id=session_id,
        report_ready=True,
        verdict=report.verdict,
        executive_summary=report.executive_summary,
        composite_scores=rollup.get("composite_scores"),
        overall_score=rollup.get("overall"),
        suggested_hr_questions=list(report.suggested_hr_questions or []),
        recommended_next_round=report.recommended_next_round,
        training_needs=list(report.training_needs or []),
        created_at=report.created_at,
    )

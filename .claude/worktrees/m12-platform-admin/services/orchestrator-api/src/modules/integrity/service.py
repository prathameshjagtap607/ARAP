import uuid

from sqlalchemy.orm import Session

from src.models.assessment_sessions import AssessmentSession
from src.models.hiring_reports import HiringReport
from src.models.integrity_flags import IntegrityFlag
from src.modules.integrity.schemas import IntegrityFlagItem, IntegritySummaryResponse


def get_integrity_summary(
    db: Session, session_id: uuid.UUID, org_id: uuid.UUID
) -> IntegritySummaryResponse:
    session = db.query(AssessmentSession).filter_by(id=session_id, org_id=org_id).first()
    if not session:
        raise LookupError("assessment session not found")

    report = db.query(HiringReport).filter_by(session_id=session_id).first()
    if not report:
        raise LookupError("integrity summary not ready — report not generated yet")

    flags = (
        db.query(IntegrityFlag)
        .filter_by(session_id=session_id)
        .order_by(IntegrityFlag.created_at)
        .all()
    )

    summary = dict(report.integrity_summary or {})

    return IntegritySummaryResponse(
        session_id=session_id,
        flagged_count=summary.get("flagged_count", 0),
        overall_risk=summary.get("overall_risk", "low"),
        human_review_required=summary.get("human_review_required", False),
        open_question=summary.get("open_question"),
        flags=[IntegrityFlagItem.model_validate(f) for f in flags],
    )

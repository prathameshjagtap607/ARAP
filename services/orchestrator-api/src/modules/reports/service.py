import uuid

from sqlalchemy.orm import Session

from src.models.assessment_sessions import AssessmentSession
from src.models.hiring_reports import HiringReport
from src.modules.reports.schemas import ReportResponse


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

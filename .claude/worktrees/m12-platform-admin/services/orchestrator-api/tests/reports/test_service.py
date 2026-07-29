import pytest
from src.modules.reports import service as report_service


def test_get_report_returns_not_ready_when_no_row(db, report_seed):
    result = report_service.get_report(db, report_seed["session"].id, report_seed["org"].id)
    assert result.report_ready is False
    assert result.verdict is None


def test_get_report_returns_report_when_row_exists(db, report_seed):
    from src.models.hiring_reports import HiringReport
    report = HiringReport(
        org_id=report_seed["org"].id,
        session_id=report_seed["session"].id,
        score_rollup={
            "composite_scores": {"Technical": 3.8},
            "overall": 3.8,
        },
        verdict="hire",
        executive_summary="Strong candidate.",
    )
    db.add(report)
    db.commit()

    result = report_service.get_report(db, report_seed["session"].id, report_seed["org"].id)
    assert result.report_ready is True
    assert result.verdict == "hire"
    assert result.executive_summary == "Strong candidate."
    assert result.overall_score == pytest.approx(3.8)

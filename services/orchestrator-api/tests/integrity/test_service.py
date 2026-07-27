import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from src.modules.integrity.service import get_integrity_summary


def _make_session(session_id, org_id):
    s = MagicMock()
    s.id = session_id
    s.org_id = org_id
    return s


def _make_report(summary):
    r = MagicMock()
    r.integrity_summary = summary
    return r


def _make_flag(flag_type="ai_generated", severity="medium"):
    f = MagicMock()
    f.id = uuid.uuid4()
    f.flag_type = flag_type
    f.severity = severity
    f.evidence = "some evidence"
    f.session_question_id = None
    f.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    return f


def _make_db(session_obj, report_obj, flags):
    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        name = str(model)
        if "AssessmentSession" in name:
            q.filter_by.return_value.first.return_value = session_obj
        elif "HiringReport" in name:
            q.filter_by.return_value.first.return_value = report_obj
        elif "IntegrityFlag" in name:
            q.filter_by.return_value.order_by.return_value.all.return_value = flags
        return q

    db.query.side_effect = query_side_effect
    return db


def test_get_integrity_summary_returns_data(session_id, org_id):
    session_obj = _make_session(session_id, org_id)
    summary = {
        "flagged_count": 1,
        "overall_risk": "low",
        "human_review_required": False,
        "flags": [],
        "open_question": "test",
    }
    report_obj = _make_report(summary)
    flag = _make_flag()
    db = _make_db(session_obj, report_obj, [flag])

    result = get_integrity_summary(db, session_id, org_id)

    assert result.session_id == session_id
    assert result.flagged_count == 1
    assert result.overall_risk == "low"
    assert len(result.flags) == 1


def test_get_integrity_summary_session_not_found(session_id, org_id):
    db = _make_db(None, None, [])
    with pytest.raises(LookupError, match="assessment session not found"):
        get_integrity_summary(db, session_id, org_id)


def test_get_integrity_summary_report_not_ready(session_id, org_id):
    session_obj = _make_session(session_id, org_id)
    db = _make_db(session_obj, None, [])
    with pytest.raises(LookupError, match="not ready"):
        get_integrity_summary(db, session_id, org_id)

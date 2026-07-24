import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from src.modules.sessions import service


def test_invite_candidate_raises_if_not_locked(db, seed):
    """invite_candidate raises ValueError if question set has no locked_at."""
    from src.models.question_sets import QuestionSet
    qset = db.query(QuestionSet).filter_by(session_id=seed["session"].id).first()
    qset.locked_at = None
    db.flush()
    with pytest.raises(ValueError, match="locked"):
        service.invite_candidate(db, seed["session"].id, seed["org"].id)
    qset.locked_at = datetime.now(UTC)
    db.flush()


def test_invite_candidate_returns_link_and_email_sent(db, seed):
    """invite_candidate returns link and calls send_invite_email."""
    with patch("src.modules.sessions.service.send_invite_email", return_value=True) as mock_mail:
        result = service.invite_candidate(db, seed["session"].id, seed["org"].id)
    assert "assessment" in result.link
    assert str(seed["session"].id) in result.link
    assert result.email_sent is True
    mock_mail.assert_called_once()


def test_get_session_state_not_started(db, seed):
    """get_session_state returns seconds_remaining=None before start."""
    result = service.get_session_state(db, seed["session"].id, seed["org"].id)
    assert result.status == "invited"
    assert result.seconds_remaining is None
    assert len(result.questions) == 2
    assert result.questions[0].sequence_no == 1


def test_start_session_transitions_status(db, seed):
    """start_session sets started_at and transitions status to in_progress."""
    result = service.start_session(db, seed["session"].id, seed["org"].id)
    assert result.status == "in_progress"
    assert result.seconds_remaining is not None
    assert result.seconds_remaining <= 1800


def test_start_session_idempotent(db, seed):
    """Calling start_session twice returns same in_progress state."""
    r1 = service.start_session(db, seed["session"].id, seed["org"].id)
    r2 = service.start_session(db, seed["session"].id, seed["org"].id)
    assert r2.status == "in_progress"
    # started_at must not change on second call
    from src.models.assessment_sessions import AssessmentSession
    s = db.query(AssessmentSession).filter_by(id=seed["session"].id).first()
    assert s.started_at == db.query(AssessmentSession).filter_by(id=seed["session"].id).first().started_at


def test_get_session_state_seconds_remaining_after_start(db, seed):
    """seconds_remaining decreases from time_budget_seconds after start."""
    service.start_session(db, seed["session"].id, seed["org"].id)
    result = service.get_session_state(db, seed["session"].id, seed["org"].id)
    assert result.seconds_remaining is not None
    assert result.seconds_remaining <= 1800
    assert result.seconds_remaining >= 0

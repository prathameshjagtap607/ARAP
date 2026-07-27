from datetime import UTC, datetime
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
    """Calling start_session twice does not overwrite started_at."""
    service.start_session(db, seed["session"].id, seed["org"].id)
    from src.models.assessment_sessions import AssessmentSession
    s_after_first = db.query(AssessmentSession).filter_by(id=seed["session"].id).first()
    started_at_first = s_after_first.started_at
    r2 = service.start_session(db, seed["session"].id, seed["org"].id)
    s_after_second = db.query(AssessmentSession).filter_by(id=seed["session"].id).first()
    db.refresh(s_after_second)
    assert r2.status == "in_progress"
    assert s_after_second.started_at == started_at_first


def test_get_session_state_seconds_remaining_after_start(db, seed):
    """seconds_remaining decreases from time_budget_seconds after start."""
    service.start_session(db, seed["session"].id, seed["org"].id)
    result = service.get_session_state(db, seed["session"].id, seed["org"].id)
    assert result.seconds_remaining is not None
    assert result.seconds_remaining <= 1800
    assert result.seconds_remaining >= 0


def test_save_answer_long_text(db, seed):
    """save_answer persists answer_text and answered_at for long_text question."""
    # ensure session is started first
    service.start_session(db, seed["session"].id, seed["org"].id)
    result = service.save_answer(
        db, seed["session"].id, seed["q1"].id, seed["org"].id, "My Python answer"
    )
    assert result.answer_text == "My Python answer"
    assert result.answered_at is not None


def test_save_answer_rejects_completed_session(db, seed):
    """save_answer raises ValueError if session is completed."""
    from src.models.assessment_sessions import AssessmentSession
    s = db.query(AssessmentSession).filter_by(id=seed["session"].id).first()
    orig_status = s.status
    s.status = "completed"
    db.flush()
    with pytest.raises(ValueError, match="completed"):
        service.save_answer(
            db, seed["session"].id, seed["q1"].id, seed["org"].id, "late answer"
        )
    s.status = orig_status
    db.flush()


def test_submit_session_marks_completed(db, seed):
    """submit_session transitions in_progress → completed."""
    service.start_session(db, seed["session"].id, seed["org"].id)
    result = service.submit_session(db, seed["session"].id, seed["org"].id)
    assert result.status == "completed"
    assert result.completed_at is not None


def test_save_answer_rejects_invited_session(db, seed):
    """save_answer raises ValueError if session has not been started."""
    from src.models.assessment_sessions import AssessmentSession
    s = db.query(AssessmentSession).filter_by(id=seed["session"].id).first()
    orig_status = s.status
    s.status = "invited"
    db.flush()
    with pytest.raises(ValueError, match="invited"):
        service.save_answer(
            db, seed["session"].id, seed["q1"].id, seed["org"].id, "should fail"
        )
    s.status = orig_status
    db.flush()


def test_submit_session_idempotent(db, seed):
    """submit_session called twice returns completed without error."""
    service.start_session(db, seed["session"].id, seed["org"].id)
    service.submit_session(db, seed["session"].id, seed["org"].id)
    r2 = service.submit_session(db, seed["session"].id, seed["org"].id)
    assert r2.status in ("completed", "expired")


def test_submit_session_expired_no_answers(db, seed):
    """submit_session with no answers and past deadline → expired."""
    from datetime import timedelta

    from src.models.assessment_sessions import AssessmentSession

    # Create a fresh session that has already expired
    from src.models.question_sets import QuestionSet
    new_session = AssessmentSession(
        org_id=seed["org"].id,
        job_assessment_id=seed["job"].id,
        candidate_id=seed["candidate"].id,
        time_budget_seconds=1,
        started_at=datetime.now(UTC) - timedelta(seconds=10),
        status="in_progress",
    )
    db.add(new_session)
    db.flush()
    new_qset = QuestionSet(
        org_id=seed["org"].id,
        session_id=new_session.id,
        generation_prompt_version="v1",
        locked_at=datetime.now(UTC),
    )
    db.add(new_qset)
    db.flush()
    db.commit()
    result = service.submit_session(db, new_session.id, seed["org"].id)
    assert result.status == "expired"

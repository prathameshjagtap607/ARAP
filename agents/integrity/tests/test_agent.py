import sys
import uuid
from unittest.mock import MagicMock, patch

_SESSION_ID = uuid.uuid4()
_ORG_ID = uuid.uuid4()

_FAKE_ORM = {
    "src": MagicMock(),
    "src.models": MagicMock(),
    "src.models.assessment_sessions": MagicMock(),
    "src.models.candidate_profiles": MagicMock(),
    "src.models.hiring_reports": MagicMock(),
    "src.models.integrity_flags": MagicMock(),
    "src.models.answer_corpus": MagicMock(),
    "src.models.question_sets": MagicMock(),
    "src.models.session_questions": MagicMock(),
}


def _make_session(candidate_profile_id=None):
    s = MagicMock()
    s.org_id = _ORG_ID
    s.id = _SESSION_ID
    s.candidate_profile_id = candidate_profile_id
    return s


def _make_db(session_obj, qset_obj, questions, report_obj=None, profile_obj=None):
    db = MagicMock()
    flags_added = []

    def query_side_effect(model):
        q = MagicMock()
        model_name = str(model)
        if "AssessmentSession" in model_name:
            q.filter_by.return_value.first.return_value = session_obj
        elif "CandidateProfile" in model_name:
            q.filter_by.return_value.first.return_value = profile_obj
        elif "HiringReport" in model_name:
            q.filter_by.return_value.first.return_value = report_obj
        elif "IntegrityFlag" in model_name:
            pass
        elif "QuestionSet" in model_name:
            q.filter_by.return_value.first.return_value = qset_obj
        elif "SessionQuestion" in model_name:
            q.filter.return_value.order_by.return_value.all.return_value = questions
        return q

    db.query.side_effect = query_side_effect

    def add_side_effect(obj):
        flags_added.append(obj)

    db.add.side_effect = add_side_effect
    return db, flags_added


def _make_q(seq=1, fmt="long_text", answer="Some long answer text here."):
    q = MagicMock()
    q.id = uuid.uuid4()
    q.sequence_no = seq
    q.answer_text = answer
    q.answer_format = fmt
    q.question = {"text": f"Q{seq}?"}
    return q


# Case 1: happy path — F01 fires, integrity_summary written to report
def test_run_integrity_checks_happy_path():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.agent import run_integrity_checks
        from agents.integrity.checks.ai_generated import FlagResult

        session_obj = _make_session()
        qset_obj = MagicMock()
        qset_obj.id = uuid.uuid4()
        questions = [_make_q(i) for i in range(1, 4)]
        report_obj = MagicMock()
        report_obj.integrity_summary = {}

        db, flags_added = _make_db(session_obj, qset_obj, questions, report_obj=report_obj)

        fake_f01_flag = FlagResult("ai_generated", "medium", "structural_std=0.5", None)

        with (
            patch("agents.integrity.checks.ai_generated.check_ai_generated", return_value=[fake_f01_flag]),
            patch("agents.integrity.checks.duplicate.check_duplicate", return_value=[]),
            patch("agents.integrity.checks.duplicate.ingest_corpus"),
            patch("agents.integrity.checks.resume_consistency.check_resume_consistency", return_value=[]),
        ):
            run_integrity_checks(session_id=_SESSION_ID, db_factory=lambda: db)

    # One IntegrityFlag added
    assert len(flags_added) >= 1
    db.commit.assert_called()
    # integrity_summary written to report
    assert report_obj.integrity_summary["flagged_count"] == 1
    assert report_obj.integrity_summary["overall_risk"] == "low"
    assert "open_question" in report_obj.integrity_summary


# Case 2: LLM failure on F03 → non-fatal, F01 flag still written
def test_f03_failure_is_nonfatal():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.agent import run_integrity_checks
        from agents.integrity.checks.ai_generated import FlagResult

        session_obj = _make_session(candidate_profile_id=uuid.uuid4())
        qset_obj = MagicMock()
        qset_obj.id = uuid.uuid4()
        questions = [_make_q()]
        report_obj = MagicMock()
        report_obj.integrity_summary = {}

        db, flags_added = _make_db(session_obj, qset_obj, questions, report_obj=report_obj, profile_obj=MagicMock())

        fake_f01_flag = FlagResult("ai_generated", "low", "structural_std=1.0", None)

        with (
            patch("agents.integrity.checks.ai_generated.check_ai_generated", return_value=[fake_f01_flag]),
            patch("agents.integrity.checks.duplicate.check_duplicate", return_value=[]),
            patch("agents.integrity.checks.duplicate.ingest_corpus"),
            patch(
                "agents.integrity.checks.resume_consistency.check_resume_consistency",
                side_effect=RuntimeError("API timeout"),
            ),
        ):
            run_integrity_checks(session_id=_SESSION_ID, db_factory=lambda: db)

    assert len(flags_added) >= 1
    db.commit.assert_called()


# Case 3: zero answered questions → no flags, empty summary
def test_zero_answers_empty_summary():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.agent import run_integrity_checks

        session_obj = _make_session()
        qset_obj = MagicMock()
        qset_obj.id = uuid.uuid4()
        report_obj = MagicMock()
        report_obj.integrity_summary = {}

        db, flags_added = _make_db(session_obj, qset_obj, [], report_obj=report_obj)

        run_integrity_checks(session_id=_SESSION_ID, db_factory=lambda: db)

    assert flags_added == []
    assert report_obj.integrity_summary["flagged_count"] == 0
    assert report_obj.integrity_summary["overall_risk"] == "low"
    assert report_obj.integrity_summary["human_review_required"] is False

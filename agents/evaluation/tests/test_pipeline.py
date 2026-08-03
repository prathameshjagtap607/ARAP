import sys
from unittest.mock import MagicMock, patch

from agents.evaluation.agent import score_answer


def _fake_tool_response(competency_scores: list[dict]):
    block = MagicMock()
    block.type = "tool_use"
    block.input = {"competency_scores": competency_scores}
    response = MagicMock()
    response.content = [block]
    return response


def test_score_answer_no_answer_returns_fallback():
    result = score_answer(
        question_text="Describe your approach to problem solving.",
        category="Technical",
        target_competencies=["problem_solving"],
        answer_text=None,
        difficulty="medium",
        job_title="Senior Engineer",
    )
    assert result["competency_scores"][0]["competency"] == "problem_solving"
    assert result["competency_scores"][0]["score"] == 1
    assert "No answer" in result["competency_scores"][0]["explanation"]


def test_score_answer_blank_answer_returns_fallback():
    result = score_answer(
        question_text="Q",
        category="Technical",
        target_competencies=["technical"],
        answer_text="   ",
        difficulty="easy",
        job_title="Engineer",
    )
    assert result["competency_scores"][0]["score"] == 1


def test_score_answer_calls_llm_and_returns_scores():
    fake_scores = [
        {
            "competency": "problem_solving",
            "score": 4,
            "explanation": "Good",
            "evidence_quote": "I structured my approach",
            "strength": "Clear reasoning",
            "improvement": "Could be more concise",
        }
    ]
    with patch("agents.evaluation.agent.call_tool", return_value={"competency_scores": fake_scores}):
        result = score_answer(
            question_text="Describe your debugging process.",
            category="Technical",
            target_competencies=["problem_solving"],
            answer_text="I structured my approach by first isolating the issue.",
            difficulty="hard",
            job_title="Senior Engineer",
        )
    assert result["competency_scores"][0]["score"] == 4
    assert result["competency_scores"][0]["competency"] == "problem_solving"


def test_score_answer_llm_failure_returns_error():
    with patch("agents.evaluation.agent.call_tool", side_effect=RuntimeError("API error")):
        result = score_answer(
            question_text="Q",
            category="Technical",
            target_competencies=["technical"],
            answer_text="Some answer",
            difficulty="easy",
            job_title="Engineer",
        )
    assert result == {"error": "evaluation_failed"}


# ---------------------------------------------------------------------------
# Pipeline integration test
# ---------------------------------------------------------------------------

import uuid

from agents.evaluation.pipeline import _resolve_answer_text, evaluation_pipeline


def _make_session_question(comp: str = "problem_solving", answer: str = "My answer") -> MagicMock:
    q = MagicMock()
    q.id = uuid.uuid4()
    q.question = {"text": "Describe your approach."}
    q.category = "Technical"
    q.target_competencies = [comp]
    q.difficulty = "medium"
    q.answer_text = answer
    q.evaluation = None
    q.answer_format = "long_text"
    q.options = None
    return q


def test_resolve_answer_text_maps_multiple_choice_letter_to_option_text():
    q = MagicMock()
    q.answer_format = "multiple_choice"
    q.options = {"A": "Use indexing", "B": "Use caching"}
    q.answer_text = "B"
    assert _resolve_answer_text(q) == "Use caching"


def test_resolve_answer_text_passthrough_for_non_multiple_choice():
    q = MagicMock()
    q.answer_format = "long_text"
    q.options = None
    q.answer_text = "A detailed free-text answer."
    assert _resolve_answer_text(q) == "A detailed free-text answer."


def test_resolve_answer_text_passthrough_when_letter_not_in_options():
    q = MagicMock()
    q.answer_format = "multiple_choice"
    q.options = {"A": "Use indexing"}
    q.answer_text = "Z"
    assert _resolve_answer_text(q) == "Z"


def test_evaluation_pipeline_scores_and_writes_report():
    session_id = uuid.uuid4()
    org_id = uuid.uuid4()

    mock_session = MagicMock()
    mock_session.org_id = org_id
    mock_session.job_assessment_id = uuid.uuid4()

    mock_job = MagicMock()
    mock_job.title = "Senior Engineer"
    mock_job.competency_weightage = {"problem_solving": 100.0}

    mock_qset = MagicMock()
    mock_qset.id = uuid.uuid4()

    q1 = _make_session_question("problem_solving", "I approach problems systematically.")
    q2 = _make_session_question("problem_solving", None)  # unanswered

    mock_db = MagicMock()
    mock_candidate = MagicMock()
    mock_candidate.name = "Alice"

    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        mock_session, mock_job, mock_qset, mock_candidate, None,  # None = no existing HiringReport
    ]
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [q1, q2]

    fake_eval = {
        "competency_scores": [{
            "competency": "problem_solving",
            "score": 4,
            "explanation": "Good",
            "evidence_quote": "I approach",
            "strength": "Systematic",
            "improvement": "Be more concise",
        }]
    }

    with patch("agents.evaluation.pipeline.score_answer", return_value=fake_eval) as mock_score, \
         patch("agents.evaluation.pipeline.roll_up", return_value={
             "competency_scores": {"problem_solving": 3.5},
             "composite_scores": {"Technical": 3.5},
             "overall": 3.5,
             "question_count": 2,
             "answered_count": 1,
         }) as mock_rollup, \
         patch("agents.evaluation.pipeline.derive_verdict", return_value="hire") as mock_verdict, \
         patch("agents.evaluation.pipeline._generate_executive_summary"), \
         patch("agents.evaluation.pipeline._run_integrity_checks"):

        db_factory = MagicMock(return_value=mock_db)
        evaluation_pipeline(session_id, db_factory)

    mock_score.assert_called()
    mock_rollup.assert_called_once()
    mock_verdict.assert_called_once_with(3.5)
    mock_db.add.assert_called()  # HiringReport added
    mock_db.commit.assert_called()


# ---------------------------------------------------------------------------
# Executive summary agent tests
# ---------------------------------------------------------------------------

from agents.evaluation.summary import generate_summary


def test_generate_summary_calls_llm_and_returns_dict():
    rollup = {
        "composite_scores": {"Technical": 3.8, "Leadership": 4.0, "Communication": 3.2, "Behavior": 3.5},
        "overall": 3.625,
    }
    fake_output = {
        "executive_summary": "Candidate shows strong technical skills.",
        "suggested_hr_questions": ["Q1", "Q2", "Q3"],
        "recommended_next_round": "Technical Panel",
        "training_needs": ["Communication clarity"],
    }
    with patch("agents.evaluation.summary.call_tool", return_value=dict(fake_output)):
        result = generate_summary("Senior Engineer", rollup, "hire", candidate_name="Alice")

    assert result["executive_summary"] == "Candidate shows strong technical skills."
    assert len(result["suggested_hr_questions"]) == 3


def test_generate_summary_returns_none_on_failure():
    with patch("agents.evaluation.summary.call_tool", side_effect=RuntimeError("fail")):
        result = generate_summary("Engineer", {}, "reject")
    assert result is None


# ---------------------------------------------------------------------------
# Integrity checks helper tests
# ---------------------------------------------------------------------------


def test_run_integrity_checks_helper_delegates():
    db = MagicMock()
    sid = uuid.uuid4()

    # Create fake module structure in sys.modules for the import
    mock_integrity_agent = MagicMock()
    mock_integrity_agent.run_integrity_checks = MagicMock()

    with patch.dict(sys.modules, {
        'agents.integrity': MagicMock(),
        'agents.integrity.agent': mock_integrity_agent
    }):
        from agents.evaluation.pipeline import _run_integrity_checks
        _run_integrity_checks(db, sid)
        mock_integrity_agent.run_integrity_checks.assert_called_once()
        call_kwargs = mock_integrity_agent.run_integrity_checks.call_args
        assert call_kwargs.kwargs["session_id"] == sid


def test_run_integrity_checks_helper_swallows_exception():
    db = MagicMock()
    sid = uuid.uuid4()

    # Create fake module structure that raises an exception
    mock_integrity_agent = MagicMock()
    mock_integrity_agent.run_integrity_checks = MagicMock(side_effect=RuntimeError("boom"))

    with patch.dict(sys.modules, {
        'agents.integrity': MagicMock(),
        'agents.integrity.agent': mock_integrity_agent
    }):
        from agents.evaluation.pipeline import _run_integrity_checks
        _run_integrity_checks(db, sid)  # must not raise


# ---------------------------------------------------------------------------
# Recommendation and report generator helper tests
# ---------------------------------------------------------------------------


def test_run_recommendation_is_nonfatal():
    db = MagicMock()
    sid = uuid.uuid4()

    mock_recommendation_agent = MagicMock()
    mock_recommendation_agent.synthesize_recommendation = MagicMock(side_effect=RuntimeError("boom"))

    with patch.dict(sys.modules, {
        'agents.recommendation': MagicMock(),
        'agents.recommendation.agent': mock_recommendation_agent,
    }):
        from agents.evaluation.pipeline import _run_recommendation
        _run_recommendation(db, sid)  # must not raise


def test_run_report_generator_is_nonfatal():
    db = MagicMock()
    sid = uuid.uuid4()

    mock_report_generator_agent = MagicMock()
    mock_report_generator_agent.generate_full_report = MagicMock(side_effect=RuntimeError("boom"))

    with patch.dict(sys.modules, {
        'agents.report_generator': MagicMock(),
        'agents.report_generator.agent': mock_report_generator_agent,
    }):
        from agents.evaluation.pipeline import _run_report_generator
        _run_report_generator(db, sid)  # must not raise

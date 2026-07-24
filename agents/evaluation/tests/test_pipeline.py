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
    with patch("agents.evaluation.agent.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _fake_tool_response(fake_scores)
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
    with patch("agents.evaluation.agent.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = RuntimeError("API error")
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

import uuid  # noqa: E402

from agents.evaluation.pipeline import evaluation_pipeline  # noqa: E402


def _make_session_question(comp: str = "problem_solving", answer: str = "My answer") -> MagicMock:
    q = MagicMock()
    q.id = uuid.uuid4()
    q.question = {"text": "Describe your approach."}
    q.category = "Technical"
    q.target_competencies = [comp]
    q.difficulty = "medium"
    q.answer_text = answer
    q.evaluation = None
    return q


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
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        mock_session, mock_job, mock_qset, None,  # None = no existing HiringReport
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
         patch("agents.evaluation.pipeline._generate_executive_summary"):

        db_factory = MagicMock(return_value=mock_db)
        evaluation_pipeline(session_id, db_factory)

    mock_score.assert_called()
    mock_rollup.assert_called_once()
    mock_verdict.assert_called_once_with(3.5)
    mock_db.add.assert_called()  # HiringReport added
    mock_db.commit.assert_called()

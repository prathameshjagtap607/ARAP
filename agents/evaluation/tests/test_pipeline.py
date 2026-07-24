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

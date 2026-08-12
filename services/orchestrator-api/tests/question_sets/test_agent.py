from unittest.mock import patch

FAKE_QUESTIONS = [
    {
        "question": "Describe your experience with Python async programming.",
        "category": "Technical",
        "target_competencies": ["Technical Accuracy", "Depth of Knowledge"],
        "difficulty": "hard",
        "answer_format": "long_text",
        "resume_reference": True,
    },
    {
        "question": "Tell me about a conflict you resolved in your team.",
        "category": "Conflict Resolution",
        "target_competencies": ["Conflict Handling", "Communication"],
        "difficulty": "medium",
        "answer_format": "long_text",
        "resume_reference": False,
    },
]

JOB_PROFILE = {
    "normalized_title": "Senior Backend Engineer",
    "role_summary": "Build scalable APIs.",
    "required_skills": ["Python"],
    "preferred_skills": ["Docker"],
    "difficulty_level": "senior",
}
CANDIDATE_PROFILE = {"summary": "Jane is a Python expert.", "skill_matrix": {}, "strengths": [], "risk_flags": []}
CATEGORY_WEIGHTAGE = {"Technical": 7, "Conflict Resolution": 3}
RISK_FLAGS = ["No direct people-management despite Manager title"]


def test_agent_returns_question_list():
    from agents.question_generation.agent import run_question_generation_agent

    with patch("agents.question_generation.agent.call_tool", return_value={"questions": FAKE_QUESTIONS}):
        result = run_question_generation_agent(
            JOB_PROFILE, CANDIDATE_PROFILE, CATEGORY_WEIGHTAGE, "senior", RISK_FLAGS, 2
        )

    assert result is not None
    assert len(result) == 2
    assert result[0]["question"] == FAKE_QUESTIONS[0]["question"]


def test_agent_returns_none_on_exception():
    from agents.question_generation.agent import run_question_generation_agent

    with patch("agents.question_generation.agent.call_tool", side_effect=Exception("API error")):
        result = run_question_generation_agent(
            JOB_PROFILE, CANDIDATE_PROFILE, CATEGORY_WEIGHTAGE, "senior", RISK_FLAGS, 2
        )

    assert result is None


def test_agent_result_contains_required_fields():
    from agents.question_generation.agent import run_question_generation_agent

    with patch("agents.question_generation.agent.call_tool", return_value={"questions": FAKE_QUESTIONS}):
        result = run_question_generation_agent(
            JOB_PROFILE, CANDIDATE_PROFILE, CATEGORY_WEIGHTAGE, "senior", RISK_FLAGS, 2
        )

    for q in result:
        for field in ("question", "category", "target_competencies", "difficulty", "answer_format", "resume_reference"):
            assert field in q, f"Missing field: {field}"


def test_agent_result_has_at_least_one_resume_reference():
    from agents.question_generation.agent import run_question_generation_agent

    with patch("agents.question_generation.agent.call_tool", return_value={"questions": FAKE_QUESTIONS}):
        result = run_question_generation_agent(
            JOB_PROFILE, CANDIDATE_PROFILE, CATEGORY_WEIGHTAGE, "senior", RISK_FLAGS, 2
        )

    assert any(q["resume_reference"] for q in result)


def test_assign_dimensions_returns_distinct_competencies_and_contexts_within_pool_size():
    """Each question must get a distinct competency/context — this is what
    prevents the model from drifting toward the same handful of familiar
    themes across a question set."""
    from agents.question_generation.agent import _assign_dimensions
    from agents.question_generation.prompts import (
        LEADERSHIP_COMPETENCIES,
        LEADERSHIP_CONTEXTS,
    )

    competencies, contexts = _assign_dimensions(10)

    assert len(competencies) == 10
    assert len(contexts) == 10
    assert len(set(competencies)) == 10  # no repeats within the first cycle
    assert len(set(contexts)) == 10
    assert set(competencies) <= set(LEADERSHIP_COMPETENCIES)
    assert set(contexts) <= set(LEADERSHIP_CONTEXTS)


def test_assign_dimensions_cycles_when_count_exceeds_pool_size():
    from agents.question_generation.agent import _assign_dimensions
    from agents.question_generation.prompts import LEADERSHIP_CONTEXTS

    # only 12 leadership contexts exist — requesting 15 must still return
    # exactly 15 valid values, cycling rather than erroring or repeating
    # a value back-to-back at the cycle boundary in an unbounded way.
    _competencies, contexts = _assign_dimensions(15)

    assert len(contexts) == 15
    assert all(c in LEADERSHIP_CONTEXTS for c in contexts)


def test_build_user_message_includes_one_assignment_per_question():
    import json

    from agents.question_generation.agent import _build_user_message

    message = _build_user_message(
        JOB_PROFILE, CANDIDATE_PROFILE, CATEGORY_WEIGHTAGE, "senior", RISK_FLAGS, 5
    )

    assignments_line = next(
        line for line in message.splitlines() if line.startswith("assigned_dimensions:")
    )
    assignments = json.loads(assignments_line[len("assigned_dimensions: "):])
    assert len(assignments) == 5
    assert [a["question_number"] for a in assignments] == [1, 2, 3, 4, 5]
    for a in assignments:
        assert "competency_area" in a
        assert "leadership_context" in a

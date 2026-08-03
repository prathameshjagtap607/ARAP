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

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


def test_find_repeated_storylines_flags_archetype_used_twice():
    from agents.question_generation.agent import _find_repeated_storylines

    questions = [
        {"question": "A team member is not meeting their performance targets. What do you do?"},
        {"question": "Your team is undergoing organizational change. How do you respond?"},
        {"question": "A colleague is struggling to keep up with their workload. What next?"},
    ]

    violations = _find_repeated_storylines(questions)

    assert "underperforming_team_member" in violations
    assert "structural_change" not in violations


def test_find_boilerplate_options_flags_reused_generic_phrase():
    from agents.question_generation.agent import _find_boilerplate_options

    generic = "I would provide guidance and support to the team."
    questions = [
        {"options": [generic, "Option B", "Option C", "Option D"]},
        {"options": [generic, "Option F", "Option G", "Option H"]},
        {"options": [generic, "Option J", "Option K", "Option L"]},
    ]

    boilerplate = _find_boilerplate_options(questions)

    assert generic.lower() in boilerplate


def test_find_boilerplate_options_flags_phrase_reused_just_twice():
    from agents.question_generation.agent import _find_boilerplate_options

    generic = "You seek input from other team members and stakeholders."
    questions = [
        {"options": [generic, "Option B", "Option C", "Option D"]},
        {"options": ["Option E", "Option F", "Option G", generic]},
    ]

    boilerplate = _find_boilerplate_options(questions)

    assert generic.lower() in boilerplate


def test_find_duplicate_option_sets_flags_reordered_identical_options():
    from agents.question_generation.agent import _find_duplicate_option_sets

    questions = [
        {"options": ["A option", "B option", "C option", "D option"]},
        {"options": ["D option", "A option", "C option", "B option"]},  # same set, shuffled
        {"options": ["E option", "F option", "G option", "H option"]},
    ]

    duplicates = _find_duplicate_option_sets(questions)

    assert duplicates == [2]


def test_run_agent_makes_exactly_one_call_even_on_failed_quality_check():
    """No auto-retry: a set that fails the quality checks (repeated
    storyline here) is still returned as-is, and the model is called
    exactly once — retrying on a failed check was found to multiply
    API/quota usage per invite, which matters more for a rate-limited
    account than accepting a first-attempt result."""
    from agents.question_generation.agent import run_question_generation_agent

    bad_set = [
        {**FAKE_QUESTIONS[0], "question": "A team member is not meeting their performance targets."},
        {**FAKE_QUESTIONS[1], "question": "Another team member is missing deadlines on their project."},
    ]

    with patch(
        "agents.question_generation.agent.call_tool",
        return_value={"questions": bad_set},
    ) as mock_call:
        result = run_question_generation_agent(
            JOB_PROFILE, CANDIDATE_PROFILE, CATEGORY_WEIGHTAGE, "senior", RISK_FLAGS, 2
        )

    assert mock_call.call_count == 1
    assert result == bad_set


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

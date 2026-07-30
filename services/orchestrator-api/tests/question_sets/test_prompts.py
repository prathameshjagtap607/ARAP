from agents.question_generation.prompts import QUESTION_GENERATION_TOOL


def test_answer_format_is_restricted_to_multiple_choice_only():
    props = QUESTION_GENERATION_TOOL["input_schema"]["properties"]["questions"]["items"]["properties"]
    assert props["answer_format"]["enum"] == ["multiple_choice"]


def test_options_is_required_when_mcq_only():
    required = QUESTION_GENERATION_TOOL["input_schema"]["properties"]["questions"]["items"]["required"]
    assert "options" in required

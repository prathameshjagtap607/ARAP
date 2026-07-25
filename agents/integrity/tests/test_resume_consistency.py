import sys
import uuid
from unittest.mock import MagicMock, patch

_FAKE_ORM = {
    "src": MagicMock(),
    "src.models": MagicMock(),
}


def _make_q(seq, text, fmt="long_text"):
    q = MagicMock()
    q.id = uuid.uuid4()
    q.sequence_no = seq
    q.answer_text = text
    q.answer_format = fmt
    q.question = {"text": f"Question {seq}?"}
    return q


def _make_profile(skill_matrix=None, experience_matrix=None):
    p = MagicMock()
    p.skill_matrix = skill_matrix or {"Python": "advanced", "Go": "intermediate"}
    p.experience_matrix = experience_matrix or {
        "Acme Corp": {"title": "Backend Engineer", "years": 3}
    }
    return p


def _make_tool_response(discrepancies):
    block = MagicMock()
    block.type = "tool_use"
    block.input = {"discrepancies": discrepancies}
    resp = MagicMock()
    resp.content = [block]
    return resp


# Case 1: all claims present in resume → no flags
def test_all_claims_present_no_flag():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.checks.resume_consistency import check_resume_consistency

        questions = [_make_q(1, "I used Python and Go extensively at Acme Corp.")]
        profile = _make_profile()

        with patch("agents.integrity.checks.resume_consistency.anthropic.Anthropic") as mock_a:
            mock_a.return_value.messages.create.return_value = _make_tool_response([
                {
                    "claim": "Used Python",
                    "present_in_resume": True,
                    "conflict_type": "skill_absent",
                    "evidence": "Python listed in skill_matrix.",
                    "answer_sequence_no": 1,
                }
            ])
            result = check_resume_consistency(questions, profile)

    assert result == []


# Case 2: skill claim absent → flag medium
def test_skill_absent_flag_medium():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.checks.resume_consistency import check_resume_consistency

        questions = [_make_q(1, "I have 5 years of Rust experience.")]
        profile = _make_profile()  # Rust not in skill_matrix

        with patch("agents.integrity.checks.resume_consistency.anthropic.Anthropic") as mock_a:
            mock_a.return_value.messages.create.return_value = _make_tool_response([
                {
                    "claim": "5 years of Rust",
                    "present_in_resume": False,
                    "conflict_type": "skill_absent",
                    "evidence": "Rust not found in skill_matrix.",
                    "answer_sequence_no": 1,
                }
            ])
            result = check_resume_consistency(questions, profile)

    assert len(result) == 1
    assert result[0].flag_type == "resume_inconsistency"
    assert result[0].severity == "medium"
    assert result[0].session_question_id == questions[0].id


# Case 3: timeline conflict → flag high
def test_timeline_conflict_flag_high():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.checks.resume_consistency import check_resume_consistency

        questions = [_make_q(2, "I led the team at Acme for 7 years starting in 2010.")]
        profile = _make_profile()

        with patch("agents.integrity.checks.resume_consistency.anthropic.Anthropic") as mock_a:
            mock_a.return_value.messages.create.return_value = _make_tool_response([
                {
                    "claim": "7 years at Acme from 2010",
                    "present_in_resume": False,
                    "conflict_type": "timeline_conflict",
                    "evidence": "Resume shows 3 years at Acme Corp.",
                    "answer_sequence_no": 2,
                }
            ])
            result = check_resume_consistency(questions, profile)

    assert len(result) == 1
    assert result[0].severity == "high"


# Case 4: no long_text questions → skip, no LLM call
def test_no_long_text_skips_llm():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.checks.resume_consistency import check_resume_consistency

        questions = [_make_q(1, "Yes.", fmt="short_text")]
        profile = _make_profile()

        with patch("agents.integrity.checks.resume_consistency.anthropic.Anthropic") as mock_a:
            result = check_resume_consistency(questions, profile)
            mock_a.return_value.messages.create.assert_not_called()

    assert result == []

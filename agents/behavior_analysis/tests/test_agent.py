import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_orm_imports():
    """Mock the ORM model imports that occur inside infer_behavior."""
    fake_models = {
        'src': MagicMock(),
        'src.models': MagicMock(),
        'src.models.assessment_sessions': MagicMock(),
        'src.models.behavior_profiles': MagicMock(),
        'src.models.question_sets': MagicMock(),
        'src.models.session_questions': MagicMock(),
    }
    with patch.dict(sys.modules, fake_models):
        yield


_SESSION_ID = uuid.uuid4()

_FAKE_SIGNALS = {
    "language_patterns": "Uses 'I' assertively; directive.",
    "decision_framing": "Data-driven; cites metrics.",
    "response_structure": "Structured with STAR framing.",
    "stress_response": "Stays methodical; prioritises ruthlessly.",
    "conflict_eq_patterns": "Focuses on shared goals; de-escalates.",
    "cross_answer_themes": "Ownership and accountability recurring.",
}

_FAKE_PROFILE = {
    "disc_style": {"primary": "D", "secondary": "C", "confidence": 0.8, "rationale": "Assertive language."},
    "big_five": {
        "openness": {"direction": "high", "evidence": "Embraces new approaches."},
        "conscientiousness": {"direction": "high", "evidence": "Cites planning and follow-through."},
        "extraversion": {"direction": "moderate", "evidence": "Collaborative but task-focused."},
        "agreeableness": {"direction": "moderate", "evidence": "Cooperative under pressure."},
        "emotional_stability": {"direction": "high", "evidence": "Calm under stress."},
    },
    "leadership_style": "Directive / results-oriented",
    "decision_style": "Analytical with iterative validation",
    "communication_style": "Direct and structured",
    "work_style": "Independent executor with clear scope",
    "stress_signal": "Methodical prioritisation; no degradation observed.",
    "eq_signal": "Focuses on shared goals; de-escalates proactively.",
    "team_compatibility_signal": "Recruiter discussion prompt: Candidate prefers autonomous work with clear KPIs.",
}


def _make_db(session_obj, qset_obj, questions):
    db = MagicMock()
    profiles_stored = []

    def query_side_effect(model):
        q = MagicMock()

        if "AssessmentSession" in str(model):
            q.filter_by.return_value.first.return_value = session_obj
        elif "BehaviorProfile" in str(model):
            q.filter_by.return_value.first.return_value = None
            def _add(obj):
                profiles_stored.append(obj)
            db.add.side_effect = _add
        elif "QuestionSet" in str(model):
            q.filter_by.return_value.first.return_value = qset_obj
        elif "SessionQuestion" in str(model):
            # Chain: db.query(SessionQuestion).filter(...).order_by(...).all()
            q.filter.return_value.order_by.return_value.all.return_value = questions
        return q

    db.query.side_effect = query_side_effect
    return db, profiles_stored


# ---------------------------------------------------------------------------
# Test 1: Happy path — 5 answered questions → profile written
# ---------------------------------------------------------------------------

def test_infer_behavior_happy_path():
    from types import SimpleNamespace

    from agents.behavior_analysis.agent import infer_behavior

    session_obj = MagicMock()
    session_obj.org_id = uuid.uuid4()
    qset_obj = MagicMock()
    qset_obj.id = uuid.uuid4()

    questions = []
    for i in range(5):
        q = MagicMock()
        q.sequence_no = i + 1
        q.category = ["Behavioral", "Stress", "Technical", "Conflict Resolution", "Teamwork"][i]
        q.question = {"text": f"Question {i+1}?"}
        q.answer_text = f"Answer {i+1} with enough content to analyze."
        questions.append(q)

    db, profiles_stored = _make_db(session_obj, qset_obj, questions)

    call_count = [0]
    def fake_call_tool(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return dict(_FAKE_SIGNALS)
        return dict(_FAKE_PROFILE)

    def mock_behavior_profile_class(**kwargs):
        # Create an object that stores the kwargs as attributes
        obj = SimpleNamespace(**kwargs)
        return obj

    with (
        patch("agents.behavior_analysis.agent.call_tool", side_effect=fake_call_tool),
        patch("agents.behavior_analysis.agent.Session"),
        patch("src.models.behavior_profiles.BehaviorProfile", side_effect=mock_behavior_profile_class),
    ):
        infer_behavior(
            session_id=_SESSION_ID,
            db_factory=lambda: db,
        )

    assert len(profiles_stored) == 1
    profile = profiles_stored[0]
    assert profile.disc_style["primary"] == "D"
    assert profile.big_five["openness"]["direction"] == "high"
    assert profile.leadership_style == "Directive / results-oriented"
    assert profile.team_compatibility_signal.startswith("Recruiter discussion prompt:")
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Test 2: No answered questions → returns without writing anything
# ---------------------------------------------------------------------------

def test_infer_behavior_no_answers():
    from agents.behavior_analysis.agent import infer_behavior

    session_obj = MagicMock()
    session_obj.org_id = uuid.uuid4()
    qset_obj = MagicMock()
    qset_obj.id = uuid.uuid4()

    db, profiles_stored = _make_db(session_obj, qset_obj, [])  # empty question list

    with patch("agents.behavior_analysis.agent.call_tool") as mock_call_tool:
        infer_behavior(session_id=_SESSION_ID, db_factory=lambda: db)
        mock_call_tool.assert_not_called()

    assert len(profiles_stored) == 0
    db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: LLM failure on Pass 1 → exception caught, no crash, rollback called
# ---------------------------------------------------------------------------

def test_infer_behavior_llm_failure():
    from agents.behavior_analysis.agent import infer_behavior

    session_obj = MagicMock()
    session_obj.org_id = uuid.uuid4()
    qset_obj = MagicMock()
    qset_obj.id = uuid.uuid4()

    questions = [MagicMock()]
    questions[0].sequence_no = 1
    questions[0].category = "Behavioral"
    questions[0].question = {"text": "Tell me about yourself."}
    questions[0].answer_text = "I am a hard worker."

    db, profiles_stored = _make_db(session_obj, qset_obj, questions)

    with patch("agents.behavior_analysis.agent.call_tool", side_effect=RuntimeError("API timeout")):
        # Should not raise
        infer_behavior(session_id=_SESSION_ID, db_factory=lambda: db)

    assert len(profiles_stored) == 0
    db.rollback.assert_called_once()
    db.commit.assert_not_called()

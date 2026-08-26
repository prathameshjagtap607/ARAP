import sys
import uuid
from unittest.mock import MagicMock, patch

_SESSION_ID = uuid.uuid4()
_ORG_ID = uuid.uuid4()

_FAKE_ORM = {
    "src": MagicMock(),
    "src.models": MagicMock(),
    "src.models.assessment_sessions": MagicMock(),
    "src.models.behavior_profiles": MagicMock(),
    "src.models.candidates": MagicMock(),
    "src.models.hiring_reports": MagicMock(),
    "src.models.job_assessments": MagicMock(),
}

_ROLLUP = {
    "competency_scores": {"technical": 3.8, "communication": 3.2},
    "composite_scores": {"Technical": 3.8, "Communication": 3.2, "Leadership": 3.0, "Behavior": 3.5},
    "overall": 3.375,
    "answered_count": 8,
    "question_count": 10,
}

_INTEGRITY_LOW = {"overall_risk": "low", "flagged_count": 0}
_INTEGRITY_HIGH = {"overall_risk": "high", "flagged_count": 2}


def _make_db(session_obj, report_obj, job_obj, behavior_obj=None, candidate_obj=None):
    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        name = str(model)
        if "AssessmentSession" in name:
            q.filter_by.return_value.first.return_value = session_obj
        elif "BehaviorProfile" in name:
            q.filter_by.return_value.first.return_value = behavior_obj
        elif "Candidate" in name:
            q.filter_by.return_value.first.return_value = candidate_obj
        elif "HiringReport" in name:
            q.filter_by.return_value.first.return_value = report_obj
        elif "JobAssessment" in name:
            q.filter_by.return_value.first.return_value = job_obj
        return q

    db.query.side_effect = query_side_effect
    return db


def _make_session():
    s = MagicMock()
    s.org_id = _ORG_ID
    s.candidate_id = uuid.uuid4()
    s.job_assessment_id = uuid.uuid4()
    return s


def _make_report(rollup, integrity):
    r = MagicMock()
    r.score_rollup = rollup
    r.integrity_summary = integrity
    r.verdict = "hire"
    r.salary_band = None
    r.ai_confidence_score = None
    r.suggested_ceo_questions = []
    r.training_needs = []
    return r


def _make_job():
    j = MagicMock()
    j.title = "Senior Engineer"
    j.difficulty_level = "senior"
    j.role_family = "engineering"
    j.required_skills = ["Python", "SQL"]
    j.experience_min = 5
    j.experience_max = 8
    return j


def _fake_llm_response(tool_output: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.input = tool_output
    resp = MagicMock()
    resp.content = [block]
    return resp


_TOOL_OUTPUT = {
    "verdict_reasoning": "Strong technical scores at 3.8 support a hire recommendation.",
    "salary_band": "L4 / Senior",
    "salary_band_rationale": "Senior difficulty level with 3.8 technical score.",
    "training_needs": [{"area": "Leadership", "priority": "medium"}],
    "suggested_ceo_questions": ["Q1?", "Q2?", "Q3?"],
}


# Case 1: happy path — all DB fields written
def test_synthesize_recommendation_happy_path():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.recommendation.agent import synthesize_recommendation

        session_obj = _make_session()
        report_obj = _make_report(_ROLLUP, _INTEGRITY_LOW)
        job_obj = _make_job()
        behavior_obj = MagicMock()
        behavior_obj.disc_style = {"primary": "D", "secondary": "I", "confidence": 0.8}
        candidate_obj = MagicMock(); candidate_obj.name = "Alice"

        db = _make_db(session_obj, report_obj, job_obj, behavior_obj, candidate_obj)

        with patch("agents.recommendation.agent.call_tool", return_value=dict(_TOOL_OUTPUT)):
            synthesize_recommendation(session_id=_SESSION_ID, db_factory=lambda: db)

    assert report_obj.salary_band == "L4 / Senior"
    assert report_obj.suggested_ceo_questions == ["Q1?", "Q2?", "Q3?"]
    assert report_obj.ai_confidence_score is not None
    assert len(report_obj.training_needs) >= 1
    db.commit.assert_called()


# Case 2: integrity risk=high → confidence penalized (< 70)
def test_confidence_penalized_on_high_integrity_risk():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.recommendation.agent import _compute_confidence

    score = _compute_confidence(_ROLLUP, _INTEGRITY_HIGH, has_behavior=True)
    # integrity factor = 0.3, so weighted contribution is low
    assert score < 80.0


# Case 3: no behavior profile → confidence factor = 0.7 (not 1.0)
def test_confidence_lower_without_behavior_profile():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.recommendation.agent import _compute_confidence

    with_behavior = _compute_confidence(_ROLLUP, _INTEGRITY_LOW, has_behavior=True)
    without_behavior = _compute_confidence(_ROLLUP, _INTEGRITY_LOW, has_behavior=False)
    assert without_behavior < with_behavior


# Case 3b: DISC confidence drives the score, so it varies per candidate
# instead of silently collapsing to the same constant for everyone — this
# was the actual bug (every DISC-only report showed "AI Confidence Score:
# 91.0" regardless of candidate, because the old per-competency-score
# consistency input this formula relied on no longer exists post-DISC-pivot
# and was always falling back to the same fixed default).
def test_confidence_varies_with_disc_confidence():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.recommendation.agent import _compute_confidence

    high_disc_confidence = _compute_confidence(
        _ROLLUP, _INTEGRITY_LOW, has_behavior=True, disc_confidence=0.9
    )
    low_disc_confidence = _compute_confidence(
        _ROLLUP, _INTEGRITY_LOW, has_behavior=True, disc_confidence=0.3
    )
    assert high_disc_confidence != low_disc_confidence
    assert high_disc_confidence > low_disc_confidence


# Case 4: LLM failure → non-fatal, prior report fields unchanged
def test_llm_failure_is_nonfatal():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.recommendation.agent import synthesize_recommendation

        session_obj = _make_session()
        report_obj = _make_report(_ROLLUP, _INTEGRITY_LOW)
        report_obj.salary_band = "original"
        job_obj = _make_job()
        candidate_obj = MagicMock(); candidate_obj.name = "Alice"

        db = _make_db(session_obj, report_obj, job_obj, candidate_obj=candidate_obj)

        with patch("agents.recommendation.agent.call_tool", side_effect=RuntimeError("API down")):
            synthesize_recommendation(session_id=_SESSION_ID, db_factory=lambda: db)

    # salary_band unchanged (rollback was called, not commit)
    assert report_obj.salary_band == "original"

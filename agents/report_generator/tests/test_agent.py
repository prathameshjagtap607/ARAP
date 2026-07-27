import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest

_SESSION_ID = uuid.uuid4()
_ORG_ID = uuid.uuid4()

_FAKE_ORM = {
    "src": MagicMock(),
    "src.models": MagicMock(),
    "src.models.assessment_sessions": MagicMock(),
    "src.models.behavior_profiles": MagicMock(),
    "src.models.candidates": MagicMock(),
    "src.models.candidate_profiles": MagicMock(),
    "src.models.hiring_reports": MagicMock(),
    "src.models.job_assessments": MagicMock(),
    "src.models.question_sets": MagicMock(),
    "src.models.session_questions": MagicMock(),
}

_ROLLUP = {
    "competency_scores": {"technical": 3.8, "communication": 3.2},
    "composite_scores": {"Technical": 3.8, "Communication": 3.2, "Leadership": 3.0, "Behavior": 3.5},
    "overall": 3.375,
    "answered_count": 8,
    "question_count": 10,
}

_NARRATIVE_OUTPUT = {
    "executive_summary": "Strong hire based on technical scores.",
    "candidate_overview": "Alice is an experienced engineer.",
    "resume_summary": "5 years Python, SQL experience.",
    "interview_summary": "Performed well across most areas.",
    "culture_fit": "Aligns well with stated values.",
    "domain_knowledge": "Deep expertise in backend systems.",
    "skill_gap_analysis": "Leadership scores below bar.",
    "strengths": ['Strong problem-solving (cited from Q3: "I designed the system from scratch")'],
    "weaknesses": ['Thin on leadership examples (cited from Q5: "I mostly worked alone")'],
    "potential_risks": "Limited management experience.",
    "learning_curve_estimate": "2-3 months to full productivity.",
    "management_readiness": "Not ready for direct management yet.",
    "promotion_potential": "Strong IC track, could lead in 18 months.",
    "integrity_summary_prose": "No integrity concerns identified.",
    "final_verdict": "Hire — Strong technical profile with 3.8 Technical score supports a hire recommendation.",
}

_STRUCTURED_OUTPUT = {
    "recommended_next_round": "Technical Panel Interview",
    "training_needs_detailed": [{"area": "Leadership", "priority": "medium", "rationale": "Low leadership score."}],
    "suggested_hr_questions": ["Q1?", "Q2?", "Q3?"],
    "suggested_ceo_questions": ["CQ1?", "CQ2?", "CQ3?"],
}


def _fake_llm_response(tool_output):
    block = MagicMock()
    block.type = "tool_use"
    block.input = tool_output
    resp = MagicMock()
    resp.content = [block]
    return resp


def _make_session():
    s = MagicMock()
    s.org_id = _ORG_ID
    s.candidate_id = uuid.uuid4()
    s.job_assessment_id = uuid.uuid4()
    s.candidate_profile_id = uuid.uuid4()
    return s


def _make_report(confidence=72.0):
    r = MagicMock()
    r.score_rollup = _ROLLUP
    r.integrity_summary = {"overall_risk": "low", "flagged_count": 0, "flags": []}
    r.verdict = "hire"
    r.ai_confidence_score = confidence
    r.salary_band = "L4 / Senior"
    r.salary_band_rationale = "Good scores."
    r.verdict_reasoning = "Strong technical."
    r.suggested_ceo_questions = ["CQ1?", "CQ2?", "CQ3?"]
    r.training_needs = ["Leadership (medium)"]
    r.full_report = {}
    r.executive_summary = None
    r.recommended_next_round = None
    r.suggested_hr_questions = []
    return r


def _make_db(session_obj, report_obj, job_obj, behavior_obj=None, candidate_obj=None,
             candidate_profile_obj=None, questions=None, qset_obj=None, historical_reports=None):
    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        name = str(model)
        if "AssessmentSession" in name:
            q.filter_by.return_value.first.return_value = session_obj
        elif "BehaviorProfile" in name:
            q.filter_by.return_value.first.return_value = behavior_obj
        elif "Candidate" in name and "Profile" not in name:
            q.filter_by.return_value.first.return_value = candidate_obj
        elif "CandidateProfile" in name:
            q.filter_by.return_value.first.return_value = candidate_profile_obj
        elif "HiringReport" in name:
            # first call returns current report; join query returns historical
            mock_q = MagicMock()
            mock_q.filter_by.return_value.first.return_value = report_obj
            mock_q.join.return_value.filter.return_value.all.return_value = historical_reports or []
            return mock_q
        elif "JobAssessment" in name:
            q.filter_by.return_value.first.return_value = job_obj
        elif "QuestionSet" in name:
            q.filter_by.return_value.first.return_value = qset_obj
        elif "SessionQuestion" in name:
            q.filter.return_value.order_by.return_value.all.return_value = questions or []
        return q

    db.query.side_effect = query_side_effect
    return db


def _make_job():
    j = MagicMock()
    j.title = "Senior Engineer"
    j.difficulty_level = "senior"
    j.role_family = "engineering"
    j.required_skills = ["Python"]
    j.culture_values = ["Ownership", "Collaboration"]
    return j


def _make_question(seq=1):
    q = MagicMock()
    q.sequence_no = seq
    q.category = "Technical"
    q.question = {"text": f"Question {seq}?"}
    q.answer_text = f"Answer {seq}"
    q.evaluation = {"explanation": f"Good answer {seq}", "competency_scores": []}
    return q


# Case 1: full report JSONB written with all expected top-level keys
def test_generate_full_report_writes_full_report():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.report_generator.agent import generate_full_report

        session_obj = _make_session()
        report_obj = _make_report()
        job_obj = _make_job()
        candidate_obj = MagicMock(); candidate_obj.name = "Alice"
        candidate_profile_obj = MagicMock(); candidate_profile_obj.summary = "Experienced engineer."
        qset_obj = MagicMock(); qset_obj.id = uuid.uuid4()
        questions = [_make_question(i) for i in range(1, 4)]

        db = _make_db(session_obj, report_obj, job_obj,
                      candidate_obj=candidate_obj,
                      candidate_profile_obj=candidate_profile_obj,
                      questions=questions, qset_obj=qset_obj)

        responses = [_fake_llm_response(_NARRATIVE_OUTPUT), _fake_llm_response(_STRUCTURED_OUTPUT)]
        with patch("anthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value.messages.create.side_effect = responses
            generate_full_report(session_id=_SESSION_ID, db_factory=lambda: db)

    full = report_obj.full_report
    assert "executive_summary" in full
    assert "final_verdict" in full
    assert "scores" in full
    assert "meta" in full
    assert "integrity_summary" in full
    db.commit.assert_called()


# Case 2: requires_human_review=True when ai_confidence_score < 60
def test_requires_human_review_when_low_confidence():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.report_generator.agent import generate_full_report

        session_obj = _make_session()
        report_obj = _make_report(confidence=45.0)
        job_obj = _make_job()
        candidate_obj = MagicMock(); candidate_obj.name = "Bob"
        qset_obj = MagicMock(); qset_obj.id = uuid.uuid4()

        db = _make_db(session_obj, report_obj, job_obj,
                      candidate_obj=candidate_obj, questions=[], qset_obj=qset_obj)

        responses = [_fake_llm_response(_NARRATIVE_OUTPUT), _fake_llm_response(_STRUCTURED_OUTPUT)]
        with patch("anthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value.messages.create.side_effect = responses
            generate_full_report(session_id=_SESSION_ID, db_factory=lambda: db)

    assert report_obj.full_report["meta"]["requires_human_review"] is True


# Case 3: final_verdict is never a bare label (must be > 10 chars)
def test_final_verdict_is_not_bare_label():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.report_generator.agent import generate_full_report

        session_obj = _make_session()
        report_obj = _make_report()
        job_obj = _make_job()
        candidate_obj = MagicMock(); candidate_obj.name = "Carol"
        qset_obj = MagicMock(); qset_obj.id = uuid.uuid4()

        db = _make_db(session_obj, report_obj, job_obj,
                      candidate_obj=candidate_obj, questions=[], qset_obj=qset_obj)

        responses = [_fake_llm_response(_NARRATIVE_OUTPUT), _fake_llm_response(_STRUCTURED_OUTPUT)]
        with patch("anthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value.messages.create.side_effect = responses
            generate_full_report(session_id=_SESSION_ID, db_factory=lambda: db)

    assert len(report_obj.full_report["final_verdict"]) > 20


# Case 4: insufficient_data returned when < 3 historical reports
def test_org_historical_bar_insufficient_data():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.report_generator.agent import _get_org_historical_bar

        db = MagicMock()
        mock_q = MagicMock()
        mock_q.join.return_value.filter.return_value.all.return_value = [
            MagicMock(score_rollup={"overall": 3.5}),
            MagicMock(score_rollup={"overall": 3.8}),
        ]
        db.query.return_value = mock_q

        result = _get_org_historical_bar(db, "engineering", uuid.uuid4())

    assert result == "insufficient_data"


# Case 5: LLM failure is non-fatal
def test_generate_full_report_llm_failure_nonfatal():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.report_generator.agent import generate_full_report

        session_obj = _make_session()
        report_obj = _make_report()
        job_obj = _make_job()
        candidate_obj = MagicMock(); candidate_obj.name = "Dave"
        qset_obj = MagicMock(); qset_obj.id = uuid.uuid4()

        db = _make_db(session_obj, report_obj, job_obj,
                      candidate_obj=candidate_obj, questions=[], qset_obj=qset_obj)

        with patch("anthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value.messages.create.side_effect = RuntimeError("timeout")
            generate_full_report(session_id=_SESSION_ID, db_factory=lambda: db)

    # full_report not updated (still empty from make_report)
    assert report_obj.full_report == {}

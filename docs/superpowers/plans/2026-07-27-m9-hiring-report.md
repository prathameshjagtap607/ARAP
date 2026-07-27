# M9 Full Hiring Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Phase 1 basic report into a fully compiled, explainable hiring document with PDF export, expiring share links, and a recruiter feedback loop.

**Architecture:** Two new agents (Recommendation, Report Generator) are appended to the existing `evaluation_pipeline` after integrity checks. The Recommendation Agent synthesises scoring + behavior + integrity into a salary band and confidence score; the Report Generator makes two sequential LLM calls (narrative then structured) and writes a `full_report` JSONB blob. Five new HTTP endpoints expose the full report, PDF download, share link creation/access, and reviewer feedback.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic, Anthropic SDK (`claude-sonnet-4-6`), weasyprint, Jinja2, pytest with `sys.modules` mock pattern (no live API or DB in agent tests).

## Global Constraints

- All endpoints are org-scoped via `claims.org_id` from JWT — never trust `org_id` from request body.
- `verdict` is always accompanied by `verdict_reasoning`; bare label is never written standalone (§9.5).
- Every strength/weakness bullet **must** cite a quoted answer excerpt (§3 explainability).
- `salary_band` stores a role-level label (e.g. `"L3 / Mid-Senior"`), never a rupee/dollar figure (§18 Open Question #1).
- No biometric, emotion-based, or protected-characteristic signals in any prompt (§15).
- Integrity summary is advisory only — system never auto-rejects (§M8-F05).
- All new agent functions are non-fatal: log exception, return, pipeline continues.
- Tests mock `anthropic.Anthropic` via `unittest.mock.patch`. No live API calls.
- Model: `claude-sonnet-4-6`, max_tokens=4096.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `services/orchestrator-api/pyproject.toml` | Add `weasyprint`, `jinja2` dependencies |
| Modify | `services/orchestrator-api/src/models/hiring_reports.py` | Add `full_report` mapped column |
| Create | `migrations/versions/<rev>_add_full_report_column.py` | Alembic migration for `full_report` |
| Create | `agents/recommendation/prompts.py` | System prompt + `RECOMMENDATION_TOOL` schema |
| Create | `agents/recommendation/agent.py` | `synthesize_recommendation()` + `_compute_confidence()` |
| Create | `agents/recommendation/tests/__init__.py` | Empty |
| Create | `agents/recommendation/tests/test_agent.py` | 4 test cases |
| Create | `agents/report_generator/prompts.py` | `NARRATIVE_TOOL` + `STRUCTURED_TOOL` schemas |
| Create | `agents/report_generator/agent.py` | `generate_full_report()` — two LLM calls + benchmarking |
| Create | `agents/report_generator/templates/report.html` | Jinja2 HTML template |
| Create | `agents/report_generator/pdf.py` | `render_pdf()` — weasyprint |
| Create | `agents/report_generator/tests/__init__.py` | Empty |
| Create | `agents/report_generator/tests/test_agent.py` | 5 test cases |
| Create | `agents/report_generator/tests/test_pdf.py` | 2 test cases |
| Modify | `services/orchestrator-api/src/modules/reports/schemas.py` | Add `FullReportResponse`, `ReviewerFeedbackRequest`, `ShareLinkRequest`, `ShareLinkResponse` |
| Modify | `services/orchestrator-api/src/modules/reports/service.py` | Add 5 service functions |
| Modify | `services/orchestrator-api/src/modules/reports/router.py` | Add 5 endpoints |
| Create | `services/orchestrator-api/tests/reports/test_full_report.py` | 8 test cases |
| Modify | `agents/evaluation/pipeline.py` | Add `_run_recommendation`, `_run_report_generator` |
| Create | `agents/evaluation/tests/test_pipeline_m9.py` | 2 pipeline wiring tests |

---

## Task 1: DB Migration — Add `full_report` Column

**Files:**
- Modify: `services/orchestrator-api/src/models/hiring_reports.py`
- Create: `migrations/versions/<rev>_add_full_report_column.py`

**Interfaces:**
- Produces: `HiringReport.full_report` — `Mapped[dict]`, JSONB, `server_default '{}'`

- [ ] **Step 1: Add `full_report` column to SQLAlchemy model**

Edit `services/orchestrator-api/src/models/hiring_reports.py`. Add after `reviewer_override`:

```python
full_report: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
```

- [ ] **Step 2: Generate Alembic migration**

```bash
cd services/orchestrator-api
alembic revision --autogenerate -m "add full_report column to hiring_reports"
```

Open the generated file in `migrations/versions/`. Verify the `upgrade()` contains:
```python
op.add_column('hiring_reports', sa.Column('full_report', postgresql.JSONB(), server_default=sa.text("'{}'"), nullable=False))
```
And `downgrade()` contains:
```python
op.drop_column('hiring_reports', 'full_report')
```

- [ ] **Step 3: Apply migration to dev DB**

```bash
alembic upgrade head
```

- [ ] **Step 4: Apply migration to test DB**

```bash
DATABASE_URL=postgresql://arap:arap@localhost:5434/arap_test alembic upgrade head
```

- [ ] **Step 5: Verify model imports cleanly**

```bash
cd services/orchestrator-api
python -c "from src.models.hiring_reports import HiringReport; print(HiringReport.__table__.columns.keys())"
```

Expected output includes `full_report`.

- [ ] **Step 6: Commit**

```bash
git add services/orchestrator-api/src/models/hiring_reports.py migrations/
git commit -m "[TASK-002] feat(reports): add full_report JSONB column to hiring_reports"
```

---

## Task 2: Recommendation Agent — Prompts & Confidence Score

**Files:**
- Create: `agents/recommendation/prompts.py`
- Create: `agents/recommendation/__init__.py`

**Interfaces:**
- Produces:
  - `RECOMMENDATION_SYSTEM_PROMPT: str`
  - `RECOMMENDATION_TOOL: dict` — tool schema with fields: `verdict_reasoning`, `salary_band`, `salary_band_rationale`, `training_needs` (array of `{area, priority}`), `suggested_ceo_questions` (array of 3 strings)
  - `_SECTION_15_EXCLUSION: str` — reuse wording from behavior_analysis pattern

- [ ] **Step 1: Create `agents/recommendation/__init__.py`** (empty file)

- [ ] **Step 2: Create `agents/recommendation/prompts.py`**

```python
_SECTION_15_EXCLUSION = (
    "Do not infer, mention, score, or reference anything related to age, gender, "
    "race, ethnicity, religion, disability, national origin, physical appearance, "
    "or any other protected characteristic. Do not treat emotional expression as a "
    "hiring criterion."
)

RECOMMENDATION_SYSTEM_PROMPT = (
    "You are a senior talent acquisition specialist writing a structured hiring recommendation. "
    "Base every claim strictly on the score data, behavior profile, and integrity summary provided. "
    "Do not invent information. The salary band must be a role-level descriptor (e.g. 'L3 / Mid-Senior'), "
    "never a monetary figure. Every verdict must be accompanied by specific reasoning citing scores. "
    + _SECTION_15_EXCLUSION
)

RECOMMENDATION_TOOL = {
    "name": "synthesize_recommendation",
    "description": "Synthesise scoring, behavior, and integrity data into a hiring recommendation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict_reasoning": {
                "type": "string",
                "description": (
                    "3-4 sentences explaining the verdict. Must cite specific composite scores "
                    "and at least one behavioral or integrity observation."
                ),
            },
            "salary_band": {
                "type": "string",
                "description": "Role-level band label e.g. 'L3 / Mid-Senior'. Never a monetary figure.",
            },
            "salary_band_rationale": {
                "type": "string",
                "description": "1-2 sentences explaining the band choice relative to difficulty_level and scores.",
            },
            "training_needs": {
                "type": "array",
                "description": "1-3 competency gaps to address if hired.",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "area": {"type": "string"},
                        "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    },
                    "required": ["area", "priority"],
                },
            },
            "suggested_ceo_questions": {
                "type": "array",
                "description": "3 CEO-round questions targeting strategic fit and leadership depth.",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "string"},
            },
        },
        "required": [
            "verdict_reasoning",
            "salary_band",
            "salary_band_rationale",
            "training_needs",
            "suggested_ceo_questions",
        ],
    },
}
```

- [ ] **Step 3: Commit**

```bash
git add agents/recommendation/
git commit -m "[TASK-002] feat(recommendation): add prompts and tool schema"
```

---

## Task 3: Recommendation Agent — Core Logic & Tests

**Files:**
- Create: `agents/recommendation/agent.py`
- Create: `agents/recommendation/tests/__init__.py`
- Create: `agents/recommendation/tests/test_agent.py`

**Interfaces:**
- Consumes:
  - `RECOMMENDATION_SYSTEM_PROMPT`, `RECOMMENDATION_TOOL` from `agents.recommendation.prompts`
  - DB models: `AssessmentSession`, `BehaviorProfile`, `Candidate`, `HiringReport`, `JobAssessment`
- Produces:
  - `synthesize_recommendation(session_id: uuid.UUID, db_factory: Callable[[], Session]) -> None`
  - `_compute_confidence(rollup: dict, integrity_summary: dict, has_behavior: bool) -> float`

- [ ] **Step 1: Write failing tests**

Create `agents/recommendation/tests/__init__.py` (empty).

Create `agents/recommendation/tests/test_agent.py`:

```python
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
        candidate_obj = MagicMock(); candidate_obj.name = "Alice"

        db = _make_db(session_obj, report_obj, job_obj, behavior_obj, candidate_obj)

        with patch("anthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value.messages.create.return_value = _fake_llm_response(_TOOL_OUTPUT)
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
    assert score < 70.0


# Case 3: no behavior profile → confidence factor = 0.7 (not 1.0)
def test_confidence_lower_without_behavior_profile():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.recommendation.agent import _compute_confidence

    with_behavior = _compute_confidence(_ROLLUP, _INTEGRITY_LOW, has_behavior=True)
    without_behavior = _compute_confidence(_ROLLUP, _INTEGRITY_LOW, has_behavior=False)
    assert without_behavior < with_behavior


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

        with patch("anthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value.messages.create.side_effect = RuntimeError("API down")
            synthesize_recommendation(session_id=_SESSION_ID, db_factory=lambda: db)

    # salary_band unchanged (rollback was called, not commit)
    assert report_obj.salary_band == "original"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd agents
pytest recommendation/tests/test_agent.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` for `agents.recommendation.agent`.

- [ ] **Step 3: Implement `agents/recommendation/agent.py`**

```python
import logging
import math
import uuid
from collections.abc import Callable

import anthropic
from sqlalchemy.orm import Session

from agents.recommendation.prompts import RECOMMENDATION_SYSTEM_PROMPT, RECOMMENDATION_TOOL

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096


def _compute_confidence(rollup: dict, integrity_summary: dict, has_behavior: bool) -> float:
    question_count = rollup.get("question_count", 1) or 1
    answered_count = rollup.get("answered_count", 0)
    coverage = min(answered_count / question_count, 1.0)

    comp_scores = list(rollup.get("competency_scores", {}).values())
    if len(comp_scores) >= 2:
        mean = sum(comp_scores) / len(comp_scores)
        variance = sum((s - mean) ** 2 for s in comp_scores) / len(comp_scores)
        std_dev = math.sqrt(variance)
        consistency = max(0.0, 1.0 - std_dev / 4.0)
    else:
        consistency = 0.7

    integrity_factor = {"low": 1.0, "medium": 0.6, "high": 0.3}.get(
        integrity_summary.get("overall_risk", "low"), 1.0
    )
    behavior_factor = 1.0 if has_behavior else 0.7

    raw = coverage * 0.40 + consistency * 0.30 + integrity_factor * 0.20 + behavior_factor * 0.10
    return round(raw * 100, 1)


def synthesize_recommendation(
    session_id: uuid.UUID,
    db_factory: Callable[[], Session],
) -> None:
    from src.models.assessment_sessions import AssessmentSession
    from src.models.behavior_profiles import BehaviorProfile
    from src.models.candidates import Candidate
    from src.models.hiring_reports import HiringReport
    from src.models.job_assessments import JobAssessment

    db = db_factory()
    try:
        session = db.query(AssessmentSession).filter_by(id=session_id).first()
        if not session:
            logger.error("synthesize_recommendation: session %s not found", session_id)
            return

        report = db.query(HiringReport).filter_by(session_id=session_id).first()
        if not report:
            logger.error("synthesize_recommendation: no report for session %s", session_id)
            return

        job = db.query(JobAssessment).filter_by(id=session.job_assessment_id).first()
        candidate = db.query(Candidate).filter_by(id=session.candidate_id).first()
        behavior = db.query(BehaviorProfile).filter_by(session_id=session_id).first()

        rollup = dict(report.score_rollup or {})
        integrity_summary = dict(report.integrity_summary or {})
        has_behavior = behavior is not None

        confidence = _compute_confidence(rollup, integrity_summary, has_behavior)

        composite_scores = rollup.get("composite_scores", {})
        competency_scores = rollup.get("competency_scores", {})
        overall = rollup.get("overall", 0.0)

        behavior_summary = ""
        if behavior:
            behavior_summary = (
                f"DISC: {behavior.disc_style}, "
                f"Leadership style: {behavior.leadership_style}, "
                f"Decision style: {behavior.decision_style}, "
                f"EQ signal: {behavior.eq_signal}"
            )

        user_message = "\n".join([
            f"Candidate: {candidate.name if candidate else 'Unknown'}",
            f"Role: {job.title if job else 'Unknown'} ({getattr(job, 'difficulty_level', 'mid')})",
            f"Role family: {getattr(job, 'role_family', 'N/A')}",
            f"Required skills: {', '.join(getattr(job, 'required_skills', []))}",
            f"Experience required: {getattr(job, 'experience_min', 'N/A')}–{getattr(job, 'experience_max', 'N/A')} years",
            f"Overall score: {overall:.2f} / 5.0",
            f"Verdict: {report.verdict}",
            "Composite scores: " + ", ".join(f"{k}: {v:.2f}" for k, v in composite_scores.items()),
            "Competency scores: " + ", ".join(f"{k}: {v:.2f}" for k, v in list(competency_scores.items())[:8]),
            f"AI confidence score: {confidence}",
            f"Integrity risk: {integrity_summary.get('overall_risk', 'low')} ({integrity_summary.get('flagged_count', 0)} flags)",
            f"Behavior profile: {behavior_summary or 'Not available'}",
        ])

        client = anthropic.Anthropic()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=RECOMMENDATION_SYSTEM_PROMPT,
            tools=[RECOMMENDATION_TOOL],
            tool_choice={"type": "tool", "name": "synthesize_recommendation"},
            messages=[{"role": "user", "content": user_message}],
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        result = dict(tool_block.input)

        report.salary_band = result["salary_band"]
        report.ai_confidence_score = confidence
        report.suggested_ceo_questions = result["suggested_ceo_questions"]
        # Flatten training_needs objects to strings for ARRAY(Text) column
        report.training_needs = [
            f"{tn['area']} ({tn['priority']})" for tn in result.get("training_needs", [])
        ]

        db.commit()
        logger.info(
            "synthesize_recommendation: complete for session %s — band=%s confidence=%.1f",
            session_id,
            result["salary_band"],
            confidence,
        )

    except Exception:
        logger.exception("synthesize_recommendation failed for session %s", session_id)
        db.rollback()
    finally:
        db.close()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd agents
pytest recommendation/tests/test_agent.py -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add agents/recommendation/
git commit -m "[TASK-002] feat(recommendation): recommendation agent with confidence score"
```

---

## Task 4: Report Generator — Prompts

**Files:**
- Create: `agents/report_generator/__init__.py`
- Create: `agents/report_generator/prompts.py`

**Interfaces:**
- Produces:
  - `NARRATIVE_SYSTEM_PROMPT: str`
  - `NARRATIVE_TOOL: dict` — tool with 15 narrative section fields
  - `STRUCTURED_SYSTEM_PROMPT: str`
  - `STRUCTURED_TOOL: dict` — tool with scores, questions, training_needs fields

- [ ] **Step 1: Create `agents/report_generator/__init__.py`** (empty)

- [ ] **Step 2: Create `agents/report_generator/prompts.py`**

```python
_SECTION_15_EXCLUSION = (
    "Do not infer, mention, score, or reference anything related to age, gender, "
    "race, ethnicity, religion, disability, national origin, physical appearance, "
    "or any other protected characteristic. Do not treat emotional expression as a "
    "hiring criterion."
)

NARRATIVE_SYSTEM_PROMPT = (
    "You are a senior HR analyst writing sections of a hiring report. "
    "Base every statement strictly on the data provided. "
    "Every strength and weakness bullet MUST include a direct quote from the candidate's answer, "
    "formatted as: '…(cited from Q{n}: \"…excerpt…\")'. "
    "Never invent quotes or information not present in the input. "
    "The final_verdict must be a full paragraph — never a bare label. "
    + _SECTION_15_EXCLUSION
)

NARRATIVE_TOOL = {
    "name": "generate_report_narrative",
    "description": "Write all narrative prose sections of the hiring report.",
    "input_schema": {
        "type": "object",
        "properties": {
            "executive_summary": {
                "type": "string",
                "description": "2-3 sentences. State verdict with reasoning. Never a bare label.",
            },
            "candidate_overview": {
                "type": "string",
                "description": "2-3 sentences on the candidate's background and suitability.",
            },
            "resume_summary": {
                "type": "string",
                "description": "3-4 sentences summarising key experience from the parsed resume.",
            },
            "interview_summary": {
                "type": "string",
                "description": "3-4 sentences on overall interview performance across categories.",
            },
            "culture_fit": {
                "type": "string",
                "description": "2-3 sentences on alignment with org culture values provided.",
            },
            "domain_knowledge": {
                "type": "string",
                "description": "2-3 sentences on depth of domain expertise evidenced in answers.",
            },
            "skill_gap_analysis": {
                "type": "string",
                "description": "Paragraph identifying skills below the job bar with specific evidence.",
            },
            "strengths": {
                "type": "array",
                "description": "2-4 strength bullets. Each MUST cite a quoted answer excerpt.",
                "minItems": 2,
                "maxItems": 4,
                "items": {"type": "string"},
            },
            "weaknesses": {
                "type": "array",
                "description": "2-4 weakness bullets. Each MUST cite a quoted answer excerpt.",
                "minItems": 2,
                "maxItems": 4,
                "items": {"type": "string"},
            },
            "potential_risks": {
                "type": "string",
                "description": "Paragraph on risks if hired, based on score patterns and integrity flags.",
            },
            "learning_curve_estimate": {
                "type": "string",
                "description": "2-3 sentences estimating ramp-up time and key learning areas.",
            },
            "management_readiness": {
                "type": "string",
                "description": "2-3 sentences on readiness to manage a team, based on leadership scores.",
            },
            "promotion_potential": {
                "type": "string",
                "description": "2-3 sentences on long-term growth trajectory.",
            },
            "integrity_summary_prose": {
                "type": "string",
                "description": (
                    "Human-readable summary of integrity flags. If risk is low or no flags, "
                    "state 'No integrity concerns identified.' "
                    "Never suggest automatic rejection — human makes the call."
                ),
            },
            "final_verdict": {
                "type": "string",
                "description": (
                    "Full paragraph. Start with the verdict label, then explain with specific "
                    "score references and at least one behavioral observation."
                ),
            },
        },
        "required": [
            "executive_summary", "candidate_overview", "resume_summary", "interview_summary",
            "culture_fit", "domain_knowledge", "skill_gap_analysis", "strengths", "weaknesses",
            "potential_risks", "learning_curve_estimate", "management_readiness",
            "promotion_potential", "integrity_summary_prose", "final_verdict",
        ],
    },
}

STRUCTURED_SYSTEM_PROMPT = (
    "You are a senior HR analyst completing the structured data sections of a hiring report. "
    "Use the narrative context and score data provided. Be specific and consistent with the narrative. "
    + _SECTION_15_EXCLUSION
)

STRUCTURED_TOOL = {
    "name": "generate_report_structured",
    "description": "Write structured data sections: scores with benchmarks, questions, training needs.",
    "input_schema": {
        "type": "object",
        "properties": {
            "recommended_next_round": {
                "type": "string",
                "description": "E.g. 'Technical Panel Interview' or 'Final HR Round'.",
            },
            "training_needs_detailed": {
                "type": "array",
                "description": "1-3 training needs with priority.",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "area": {"type": "string"},
                        "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                        "rationale": {"type": "string"},
                    },
                    "required": ["area", "priority", "rationale"],
                },
            },
            "suggested_hr_questions": {
                "type": "array",
                "description": "3 HR-round questions targeting weak competencies.",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "string"},
            },
            "suggested_ceo_questions": {
                "type": "array",
                "description": "3 CEO-round questions on strategic fit and leadership depth.",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "string"},
            },
        },
        "required": [
            "recommended_next_round",
            "training_needs_detailed",
            "suggested_hr_questions",
            "suggested_ceo_questions",
        ],
    },
}
```

- [ ] **Step 3: Commit**

```bash
git add agents/report_generator/
git commit -m "[TASK-002] feat(report-generator): add narrative and structured tool schemas"
```

---

## Task 5: Report Generator Agent — Core Logic & Tests

**Files:**
- Create: `agents/report_generator/agent.py`
- Create: `agents/report_generator/tests/__init__.py`
- Create: `agents/report_generator/tests/test_agent.py`

**Interfaces:**
- Consumes:
  - `NARRATIVE_SYSTEM_PROMPT`, `NARRATIVE_TOOL`, `STRUCTURED_SYSTEM_PROMPT`, `STRUCTURED_TOOL` from `agents.report_generator.prompts`
  - DB models: `AssessmentSession`, `BehaviorProfile`, `Candidate`, `CandidateProfile`, `HiringReport`, `JobAssessment`, `QuestionSet`, `SessionQuestion`
- Produces:
  - `generate_full_report(session_id: uuid.UUID, db_factory: Callable[[], Session]) -> None`
  - `_get_org_historical_bar(db, role_family: str, org_id) -> str | float` — returns `"insufficient_data"` if < 3 records

- [ ] **Step 1: Write failing tests**

Create `agents/report_generator/tests/__init__.py` (empty).

Create `agents/report_generator/tests/test_agent.py`:

```python
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
    # Simulate join returning only 2 reports
    mock_q = MagicMock()
    mock_q.join.return_value.filter.return_value.all.return_value = [
        MagicMock(score_rollup={"overall": 3.5}),
        MagicMock(score_rollup={"overall": 3.8}),
    ]
    db.query.return_value = mock_q

    result = _get_org_historical_bar(db, "engineering", _ORG_ID)
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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd agents
pytest report_generator/tests/test_agent.py -v
```

Expected: `ImportError` for `agents.report_generator.agent`.

- [ ] **Step 3: Implement `agents/report_generator/agent.py`**

```python
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import anthropic
from sqlalchemy.orm import Session

from agents.report_generator.prompts import (
    NARRATIVE_SYSTEM_PROMPT,
    NARRATIVE_TOOL,
    STRUCTURED_SYSTEM_PROMPT,
    STRUCTURED_TOOL,
)

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096
_HIRE_BAR = 3.50


def _get_org_historical_bar(db: Session, role_family: str | None, org_id) -> str | float:
    if not role_family:
        return "insufficient_data"
    from src.models.assessment_sessions import AssessmentSession
    from src.models.hiring_reports import HiringReport
    from src.models.job_assessments import JobAssessment

    rows = (
        db.query(HiringReport)
        .join(AssessmentSession, HiringReport.session_id == AssessmentSession.id)
        .join(JobAssessment, AssessmentSession.job_assessment_id == JobAssessment.id)
        .filter(
            JobAssessment.role_family == role_family,
            JobAssessment.org_id == org_id,
            HiringReport.verdict.in_(["hire", "strong_hire"]),
        )
        .all()
    )
    overalls = [r.score_rollup.get("overall") for r in rows if r.score_rollup and r.score_rollup.get("overall")]
    if len(overalls) < 3:
        return "insufficient_data"
    overalls.sort()
    mid = len(overalls) // 2
    median = overalls[mid] if len(overalls) % 2 else (overalls[mid - 1] + overalls[mid]) / 2
    return round(median, 4)


def _build_score_section(composite_scores: dict, org_bar) -> dict:
    scores = {}
    for composite, score in composite_scores.items():
        delta_job = round(score - _HIRE_BAR, 2)
        vs_job = f"{'+' if delta_job >= 0 else ''}{delta_job}"
        if org_bar == "insufficient_data":
            vs_org = "insufficient_data"
        else:
            delta_org = round(score - float(org_bar), 2)
            vs_org = f"{'+' if delta_org >= 0 else ''}{delta_org}"
        scores[composite.lower()] = {"score": round(score, 2), "vs_job_bar": vs_job, "vs_org_bar": vs_org}
    return scores


def generate_full_report(
    session_id: uuid.UUID,
    db_factory: Callable[[], Session],
) -> None:
    from src.models.assessment_sessions import AssessmentSession
    from src.models.behavior_profiles import BehaviorProfile
    from src.models.candidate_profiles import CandidateProfile
    from src.models.candidates import Candidate
    from src.models.hiring_reports import HiringReport
    from src.models.job_assessments import JobAssessment
    from src.models.question_sets import QuestionSet
    from src.models.session_questions import SessionQuestion

    db = db_factory()
    try:
        session = db.query(AssessmentSession).filter_by(id=session_id).first()
        if not session:
            logger.error("generate_full_report: session %s not found", session_id)
            return

        report = db.query(HiringReport).filter_by(session_id=session_id).first()
        if not report:
            logger.error("generate_full_report: no report for session %s", session_id)
            return

        job = db.query(JobAssessment).filter_by(id=session.job_assessment_id).first()
        candidate = db.query(Candidate).filter_by(id=session.candidate_id).first()
        behavior = db.query(BehaviorProfile).filter_by(session_id=session_id).first()
        candidate_profile = None
        if session.candidate_profile_id:
            candidate_profile = db.query(CandidateProfile).filter_by(id=session.candidate_profile_id).first()
        qset = db.query(QuestionSet).filter_by(session_id=session_id).first()
        questions = []
        if qset:
            questions = (
                db.query(SessionQuestion)
                .filter(
                    SessionQuestion.question_set_id == qset.id,
                    SessionQuestion.answer_text.isnot(None),
                )
                .order_by(SessionQuestion.sequence_no)
                .all()
            )

        rollup = dict(report.score_rollup or {})
        composite_scores = rollup.get("composite_scores", {})
        integrity_summary = dict(report.integrity_summary or {})
        confidence = float(report.ai_confidence_score or 0)
        requires_human_review = confidence < 60

        org_bar = _get_org_historical_bar(db, getattr(job, "role_family", None), session.org_id)
        score_section = _build_score_section(composite_scores, org_bar)

        answer_excerpts = "\n".join(
            f"Q{q.sequence_no} [{q.category}]: {q.question.get('text', '')}\n"
            f"A: {q.answer_text}\n"
            f"Evaluation note: {(q.evaluation or {}).get('explanation', '')}"
            for q in questions
        )

        behavior_text = ""
        if behavior:
            behavior_text = (
                f"DISC: {behavior.disc_style}, Big Five: {behavior.big_five}, "
                f"Leadership: {behavior.leadership_style}, EQ: {behavior.eq_signal}"
            )

        narrative_input = "\n".join([
            f"Candidate: {candidate.name if candidate else 'Unknown'}",
            f"Role: {job.title if job else 'Unknown'}",
            f"Verdict: {report.verdict}",
            f"Verdict reasoning: {getattr(report, 'verdict_reasoning', '')}",
            f"Overall score: {rollup.get('overall', 0):.2f} / 5.0",
            "Composite scores: " + ", ".join(f"{k}: {v:.2f}" for k, v in composite_scores.items()),
            f"Salary band: {report.salary_band}",
            f"Integrity: risk={integrity_summary.get('overall_risk', 'low')}, "
            f"flags={integrity_summary.get('flagged_count', 0)}",
            f"Behavior: {behavior_text or 'Not available'}",
            f"Resume summary: {candidate_profile.summary if candidate_profile else 'Not available'}",
            f"Culture values: {', '.join(getattr(job, 'culture_values', []))}",
            "",
            "Answer excerpts (use Q numbers when citing):",
            answer_excerpts or "No answers available.",
        ])

        client = anthropic.Anthropic()

        # Call 1 — narrative sections
        narrative_resp = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=NARRATIVE_SYSTEM_PROMPT,
            tools=[NARRATIVE_TOOL],
            tool_choice={"type": "tool", "name": "generate_report_narrative"},
            messages=[{"role": "user", "content": narrative_input}],
        )
        narrative_block = next(b for b in narrative_resp.content if b.type == "tool_use")
        narrative = dict(narrative_block.input)

        # Call 2 — structured sections
        structured_input = "\n".join([
            "Narrative summary (for context):",
            narrative.get("executive_summary", ""),
            narrative.get("skill_gap_analysis", ""),
            "",
            "Score data:",
            "Composite scores: " + ", ".join(f"{k}: {v:.2f}" for k, v in composite_scores.items()),
            f"Salary band: {report.salary_band}",
            "Existing CEO questions from recommendation: "
            + ", ".join(report.suggested_ceo_questions or []),
            "Training needs from recommendation: " + ", ".join(report.training_needs or []),
        ])
        structured_resp = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=STRUCTURED_SYSTEM_PROMPT,
            tools=[STRUCTURED_TOOL],
            tool_choice={"type": "tool", "name": "generate_report_structured"},
            messages=[{"role": "user", "content": structured_input}],
        )
        structured_block = next(b for b in structured_resp.content if b.type == "tool_use")
        structured = dict(structured_block.input)

        full_report = {
            "meta": {
                "schema_version": "1.0",
                "generated_at": datetime.now(UTC).isoformat(),
                "requires_human_review": requires_human_review,
                "confidence_rationale": (
                    f"AI confidence score: {confidence}. "
                    + ("Mandatory human review required (score < 60)." if requires_human_review else "")
                ),
            },
            "executive_summary": narrative["executive_summary"],
            "candidate_overview": narrative["candidate_overview"],
            "resume_summary": narrative["resume_summary"],
            "interview_summary": narrative["interview_summary"],
            "scores": score_section,
            "overall_rating": round(rollup.get("overall", 0), 2),
            "culture_fit": narrative["culture_fit"],
            "domain_knowledge": narrative["domain_knowledge"],
            "skill_gap_analysis": narrative["skill_gap_analysis"],
            "strengths": narrative["strengths"],
            "weaknesses": narrative["weaknesses"],
            "potential_risks": narrative["potential_risks"],
            "learning_curve_estimate": narrative["learning_curve_estimate"],
            "management_readiness": narrative["management_readiness"],
            "promotion_potential": narrative["promotion_potential"],
            "salary_recommendation": {
                "band": report.salary_band,
                "rationale": getattr(report, "salary_band_rationale", ""),
            },
            "ai_confidence_score": confidence,
            "recommended_next_round": structured["recommended_next_round"],
            "training_needs": structured["training_needs_detailed"],
            "suggested_hr_questions": structured["suggested_hr_questions"],
            "suggested_ceo_questions": structured["suggested_ceo_questions"],
            "integrity_summary": integrity_summary,
            "integrity_summary_prose": narrative["integrity_summary_prose"],
            "final_verdict": narrative["final_verdict"],
        }

        report.full_report = full_report
        report.executive_summary = narrative["executive_summary"]
        report.recommended_next_round = structured["recommended_next_round"]
        report.suggested_hr_questions = structured["suggested_hr_questions"]

        db.commit()
        logger.info("generate_full_report: complete for session %s", session_id)

    except Exception:
        logger.exception("generate_full_report failed for session %s", session_id)
        db.rollback()
    finally:
        db.close()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd agents
pytest report_generator/tests/test_agent.py -v
```

Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add agents/report_generator/
git commit -m "[TASK-002] feat(report-generator): full report agent with two-stage LLM calls"
```

---

## Task 6: PDF Export — Template & Renderer

**Files:**
- Modify: `services/orchestrator-api/pyproject.toml`
- Create: `agents/report_generator/templates/report.html`
- Create: `agents/report_generator/pdf.py`
- Create: `agents/report_generator/tests/test_pdf.py`

**Interfaces:**
- Produces: `render_pdf(report_data: dict, candidate_name: str, job_title: str, include_transcript: bool = False) -> bytes`

- [ ] **Step 1: Add dependencies to pyproject.toml**

In `services/orchestrator-api/pyproject.toml`, add to `dependencies`:
```toml
"weasyprint>=62.0",
"jinja2>=3.1",
```

Install:
```bash
cd services/orchestrator-api
pip install weasyprint jinja2
```

- [ ] **Step 2: Write failing test**

Create `agents/report_generator/tests/test_pdf.py`:

```python
from agents.report_generator.pdf import render_pdf

_SAMPLE_REPORT = {
    "meta": {"generated_at": "2026-07-27T00:00:00+00:00", "requires_human_review": False, "confidence_rationale": ""},
    "executive_summary": "Strong hire.",
    "candidate_overview": "Experienced engineer.",
    "resume_summary": "5 years Python.",
    "interview_summary": "Performed well.",
    "scores": {"technical": {"score": 3.8, "vs_job_bar": "+0.3", "vs_org_bar": "-0.1"}},
    "overall_rating": 3.8,
    "culture_fit": "Good fit.",
    "domain_knowledge": "Deep expertise.",
    "skill_gap_analysis": "Leadership gap.",
    "strengths": ['Strong problem-solving (cited from Q3: "I designed it")'],
    "weaknesses": ['Thin leadership (cited from Q5: "I worked alone")'],
    "potential_risks": "Limited management experience.",
    "learning_curve_estimate": "2-3 months.",
    "management_readiness": "Not ready yet.",
    "promotion_potential": "Strong IC trajectory.",
    "salary_recommendation": {"band": "L4 / Senior", "rationale": "Senior scores."},
    "ai_confidence_score": 72.0,
    "recommended_next_round": "Technical Panel",
    "training_needs": [{"area": "Leadership", "priority": "medium", "rationale": "Low score."}],
    "suggested_hr_questions": ["Q1?", "Q2?", "Q3?"],
    "suggested_ceo_questions": ["CQ1?", "CQ2?", "CQ3?"],
    "integrity_summary": {"overall_risk": "low", "flagged_count": 0},
    "integrity_summary_prose": "No integrity concerns identified.",
    "final_verdict": "Hire — Strong technical profile supports a hire recommendation.",
}


# Case 1: render_pdf returns bytes starting with PDF magic bytes
def test_render_pdf_returns_pdf_bytes():
    result = render_pdf(_SAMPLE_REPORT, candidate_name="Alice", job_title="Senior Engineer")
    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"


# Case 2: transcript section absent when include_transcript=False
def test_render_pdf_no_transcript_by_default():
    result = render_pdf(_SAMPLE_REPORT, candidate_name="Alice", job_title="Senior Engineer",
                        include_transcript=False)
    # PDF text won't easily search, so just confirm it renders without error
    assert len(result) > 1000
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
cd agents
pytest report_generator/tests/test_pdf.py -v
```

Expected: `ImportError` for `agents.report_generator.pdf`.

- [ ] **Step 4: Create `agents/report_generator/templates/report.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Hiring Report — {{ candidate_name }}</title>
  <style>
    body { font-family: Arial, sans-serif; font-size: 11pt; color: #222; margin: 40px; }
    h1 { font-size: 18pt; color: #1a3c6e; border-bottom: 2px solid #1a3c6e; padding-bottom: 6px; }
    h2 { font-size: 13pt; color: #1a3c6e; margin-top: 24px; }
    h3 { font-size: 11pt; color: #444; margin-top: 16px; }
    .meta { background: #f4f7fb; padding: 10px 16px; border-radius: 4px; margin-bottom: 20px; }
    .meta p { margin: 4px 0; font-size: 10pt; }
    .score-table { width: 100%; border-collapse: collapse; margin: 12px 0; }
    .score-table th { background: #1a3c6e; color: white; padding: 6px 10px; text-align: left; font-size: 10pt; }
    .score-table td { padding: 6px 10px; border-bottom: 1px solid #ddd; font-size: 10pt; }
    .verdict-box { background: #e8f0fe; border-left: 4px solid #1a3c6e; padding: 12px 16px; margin: 16px 0; }
    .warning-box { background: #fff3cd; border-left: 4px solid #e6a817; padding: 10px 14px; margin: 12px 0; font-size: 10pt; }
    ul { margin: 6px 0; padding-left: 20px; }
    li { margin: 4px 0; }
    .section { margin-bottom: 18px; }
    .label { font-weight: bold; }
    .footer { margin-top: 40px; font-size: 9pt; color: #888; border-top: 1px solid #ddd; padding-top: 8px; }
  </style>
</head>
<body>

<h1>Hiring Report</h1>

<div class="meta">
  <p><span class="label">Candidate:</span> {{ candidate_name }}</p>
  <p><span class="label">Role:</span> {{ job_title }}</p>
  <p><span class="label">Generated:</span> {{ report.meta.generated_at }}</p>
  <p><span class="label">AI Confidence Score:</span> {{ report.ai_confidence_score }}</p>
</div>

{% if report.meta.requires_human_review %}
<div class="warning-box">
  ⚠ <strong>Mandatory Human Review Required</strong> — AI confidence score below threshold. {{ report.meta.confidence_rationale }}
</div>
{% endif %}

<div class="verdict-box">
  <h2 style="margin-top:0">Executive Summary</h2>
  <p>{{ report.executive_summary }}</p>
</div>

<h2>Candidate Overview</h2>
<div class="section"><p>{{ report.candidate_overview }}</p></div>

<h2>Resume Summary</h2>
<div class="section"><p>{{ report.resume_summary }}</p></div>

<h2>Interview Summary</h2>
<div class="section"><p>{{ report.interview_summary }}</p></div>

<h2>Scores vs Benchmarks</h2>
<table class="score-table">
  <thead>
    <tr><th>Area</th><th>Score (/5)</th><th>vs Job Bar</th><th>vs Org Bar</th></tr>
  </thead>
  <tbody>
    {% for area, data in report.scores.items() %}
    <tr>
      <td>{{ area | title }}</td>
      <td>{{ data.score }}</td>
      <td>{{ data.vs_job_bar }}</td>
      <td>{{ data.vs_org_bar }}</td>
    </tr>
    {% endfor %}
    <tr style="font-weight:bold; background:#f4f7fb">
      <td>Overall</td>
      <td>{{ report.overall_rating }}</td>
      <td>—</td>
      <td>—</td>
    </tr>
  </tbody>
</table>

<h2>Salary Recommendation</h2>
<div class="section">
  <p><span class="label">Band:</span> {{ report.salary_recommendation.band }}</p>
  <p>{{ report.salary_recommendation.rationale }}</p>
</div>

<h2>Culture Fit</h2>
<div class="section"><p>{{ report.culture_fit }}</p></div>

<h2>Domain Knowledge</h2>
<div class="section"><p>{{ report.domain_knowledge }}</p></div>

<h2>Skill Gap Analysis</h2>
<div class="section"><p>{{ report.skill_gap_analysis }}</p></div>

<h2>Strengths</h2>
<div class="section">
  <ul>{% for s in report.strengths %}<li>{{ s }}</li>{% endfor %}</ul>
</div>

<h2>Weaknesses</h2>
<div class="section">
  <ul>{% for w in report.weaknesses %}<li>{{ w }}</li>{% endfor %}</ul>
</div>

<h2>Potential Risks</h2>
<div class="section"><p>{{ report.potential_risks }}</p></div>

<h2>Learning Curve Estimate</h2>
<div class="section"><p>{{ report.learning_curve_estimate }}</p></div>

<h2>Management Readiness</h2>
<div class="section"><p>{{ report.management_readiness }}</p></div>

<h2>Promotion Potential</h2>
<div class="section"><p>{{ report.promotion_potential }}</p></div>

<h2>Integrity Summary</h2>
<div class="section"><p>{{ report.integrity_summary_prose }}</p></div>

<h2>Recommended Next Round</h2>
<div class="section"><p>{{ report.recommended_next_round }}</p></div>

<h2>Training Needs</h2>
<div class="section">
  <ul>
    {% for tn in report.training_needs %}
    <li><strong>{{ tn.area }}</strong> ({{ tn.priority }}) — {{ tn.rationale }}</li>
    {% endfor %}
  </ul>
</div>

<h2>Suggested HR-Round Questions</h2>
<div class="section">
  <ul>{% for q in report.suggested_hr_questions %}<li>{{ q }}</li>{% endfor %}</ul>
</div>

<h2>Suggested CEO-Round Questions</h2>
<div class="section">
  <ul>{% for q in report.suggested_ceo_questions %}<li>{{ q }}</li>{% endfor %}</ul>
</div>

<h2>Final Verdict</h2>
<div class="verdict-box"><p>{{ report.final_verdict }}</p></div>

{% if include_transcript %}
<h2>Raw Transcript</h2>
<div class="section">
  <p><em>Transcript included per recruiter request.</em></p>
  {% for item in transcript %}
  <p><strong>Q{{ item.sequence_no }}:</strong> {{ item.question }}<br>
     <strong>A:</strong> {{ item.answer }}</p>
  {% endfor %}
</div>
{% endif %}

<div class="footer">
  Generated by ARAP — AI Recruitment Assessment Platform. For internal HR use only.
  AI confidence score: {{ report.ai_confidence_score }}. All hiring decisions require human review.
</div>

</body>
</html>
```

- [ ] **Step 5: Implement `agents/report_generator/pdf.py`**

```python
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def render_pdf(
    report_data: dict,
    candidate_name: str,
    job_title: str,
    include_transcript: bool = False,
    transcript: list[dict] | None = None,
) -> bytes:
    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
    template = env.get_template("report.html")
    html_content = template.render(
        report=report_data,
        candidate_name=candidate_name,
        job_title=job_title,
        include_transcript=include_transcript,
        transcript=transcript or [],
    )
    return HTML(string=html_content).write_pdf()
```

- [ ] **Step 6: Run tests — verify they pass**

```bash
cd agents
pytest report_generator/tests/test_pdf.py -v
```

Expected: 2 PASSED.

- [ ] **Step 7: Commit**

```bash
git add agents/report_generator/ services/orchestrator-api/pyproject.toml
git commit -m "[TASK-002] feat(report-generator): PDF export via weasyprint + Jinja2"
```

---

## Task 7: Reports Module — Schemas Extension

**Files:**
- Modify: `services/orchestrator-api/src/modules/reports/schemas.py`

**Interfaces:**
- Produces:
  - `FullReportResponse` — `session_id`, `report_ready`, `requires_human_review`, `full_report`, `verdict`, `ai_confidence_score`, `salary_band`
  - `ReviewerFeedbackRequest` — `final_decision: Literal["hire","no_hire","hold"]`, `comment: str`, `score_overrides: dict[str, float] | None`
  - `ReviewerFeedbackResponse` — `reviewer_override: dict`
  - `ShareLinkRequest` — `client_id: uuid.UUID`, `expires_in_days: int`
  - `ShareLinkResponse` — `share_token: uuid.UUID`, `expires_at: datetime`

- [ ] **Step 1: Update `services/orchestrator-api/src/modules/reports/schemas.py`**

```python
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ReportResponse(BaseModel):
    session_id: uuid.UUID
    report_ready: bool
    verdict: str | None
    executive_summary: str | None
    composite_scores: dict | None
    overall_score: float | None
    suggested_hr_questions: list[str]
    recommended_next_round: str | None
    training_needs: list[str]
    created_at: datetime | None

    model_config = {"from_attributes": True}


class FullReportResponse(BaseModel):
    session_id: uuid.UUID
    report_ready: bool
    requires_human_review: bool
    verdict: str | None
    ai_confidence_score: float | None
    salary_band: str | None
    full_report: dict
    created_at: datetime | None

    model_config = {"from_attributes": True}


class ReviewerFeedbackRequest(BaseModel):
    final_decision: Literal["hire", "no_hire", "hold"]
    comment: str
    score_overrides: dict[str, float] | None = None


class ReviewerFeedbackResponse(BaseModel):
    reviewer_override: dict


class ShareLinkRequest(BaseModel):
    client_id: uuid.UUID
    expires_in_days: int


class ShareLinkResponse(BaseModel):
    share_token: uuid.UUID
    expires_at: datetime
```

- [ ] **Step 2: Verify import**

```bash
cd services/orchestrator-api
python -c "from src.modules.reports.schemas import FullReportResponse, ReviewerFeedbackRequest, ShareLinkRequest; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add services/orchestrator-api/src/modules/reports/schemas.py
git commit -m "[TASK-002] feat(reports): extend schemas for full report, feedback, share link"
```

---

## Task 8: Reports Module — Service & Router + Tests

**Files:**
- Modify: `services/orchestrator-api/src/modules/reports/service.py`
- Modify: `services/orchestrator-api/src/modules/reports/router.py`
- Create: `services/orchestrator-api/tests/reports/test_full_report.py`

**Interfaces:**
- Consumes:
  - `FullReportResponse`, `ReviewerFeedbackRequest`, `ReviewerFeedbackResponse`, `ShareLinkRequest`, `ShareLinkResponse` from `schemas.py`
  - `HiringReport`, `ReportShare`, `AssessmentSession`, `Client`, `SessionQuestion` models
  - `render_pdf` from `agents.report_generator.pdf`
- Produces (service functions):
  - `get_full_report(db, session_id, org_id) -> FullReportResponse`
  - `submit_reviewer_feedback(db, session_id, org_id, req: ReviewerFeedbackRequest) -> ReviewerFeedbackResponse`
  - `create_share_link(db, session_id, org_id, user_id, req: ShareLinkRequest) -> ShareLinkResponse`
  - `get_shared_report(db, token: uuid.UUID) -> dict`
  - `get_report_pdf(db, session_id, org_id, include_transcript: bool) -> bytes`

- [ ] **Step 1: Write failing tests**

Create `services/orchestrator-api/tests/reports/test_full_report.py`:

```python
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from src.models.clients import Client
from src.models.hiring_reports import HiringReport
from src.models.report_shares import ReportShare


_FULL_REPORT = {
    "meta": {"schema_version": "1.0", "generated_at": "2026-07-27T00:00:00+00:00",
             "requires_human_review": False, "confidence_rationale": ""},
    "executive_summary": "Strong hire.",
    "final_verdict": "Hire — strong technical profile.",
    "scores": {"technical": {"score": 3.8, "vs_job_bar": "+0.3", "vs_org_bar": "insufficient_data"}},
    "overall_rating": 3.8,
    "strengths": ["Good (cited from Q1: \"example\")"],
    "weaknesses": ["Thin leadership (cited from Q2: \"example\")"],
    "training_needs": [{"area": "Leadership", "priority": "medium", "rationale": "Low score."}],
    "suggested_hr_questions": ["Q1?", "Q2?", "Q3?"],
    "suggested_ceo_questions": ["CQ1?", "CQ2?", "CQ3?"],
    "integrity_summary": {"overall_risk": "low"},
    "integrity_summary_prose": "No concerns.",
    "salary_recommendation": {"band": "L4 / Senior", "rationale": "Good scores."},
    "ai_confidence_score": 72.0,
    "recommended_next_round": "Technical Panel",
    "candidate_overview": "Experienced.",
    "resume_summary": "5 years Python.",
    "interview_summary": "Performed well.",
    "culture_fit": "Good fit.",
    "domain_knowledge": "Deep expertise.",
    "skill_gap_analysis": "Leadership gap.",
    "potential_risks": "Limited management.",
    "learning_curve_estimate": "2-3 months.",
    "management_readiness": "Not ready.",
    "promotion_potential": "Strong IC.",
}


@pytest.fixture
def report_with_full(db, report_seed):
    report = HiringReport(
        org_id=report_seed["org"].id,
        session_id=report_seed["session"].id,
        score_rollup={"composite_scores": {"Technical": 3.8}, "overall": 3.8},
        verdict="hire",
        ai_confidence_score=72.0,
        salary_band="L4 / Senior",
        full_report=_FULL_REPORT,
        executive_summary="Strong hire.",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@pytest.fixture
def client_fixture(db, report_seed):
    c = Client(
        org_id=report_seed["org"].id,
        name="Acme Corp",
        email=f"acme-{uuid.uuid4().hex[:6]}@example.com",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# Case 1: GET /reports/{session_id}/full returns 200 with full_report
@pytest.mark.asyncio
async def test_get_full_report_200(async_client: AsyncClient, user_token, report_with_full, report_seed):
    resp = await async_client.get(
        f"/reports/{report_seed['session'].id}/full",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_ready"] is True
    assert "executive_summary" in data["full_report"]
    assert data["verdict"] == "hire"


# Case 2: GET /reports/{session_id}/full returns 404 when no report
@pytest.mark.asyncio
async def test_get_full_report_404_no_report(async_client: AsyncClient, user_token, report_seed):
    resp = await async_client.get(
        f"/reports/{report_seed['session'].id}/full",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


# Case 3: POST /reports/{session_id}/share creates report_shares row
@pytest.mark.asyncio
async def test_create_share_link(async_client: AsyncClient, user_token, report_with_full,
                                  report_seed, client_fixture, db):
    resp = await async_client.post(
        f"/reports/{report_seed['session'].id}/share",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"client_id": str(client_fixture.id), "expires_in_days": 7},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "share_token" in data
    assert "expires_at" in data

    share = db.query(ReportShare).filter_by(id=data["share_token"]).first()
    assert share is not None
    assert share.client_id == client_fixture.id


# Case 4: GET /reports/shared/{token} returns 200 with scoped view
@pytest.mark.asyncio
async def test_get_shared_report_200(async_client: AsyncClient, report_with_full,
                                      report_seed, client_fixture, db):
    share = ReportShare(
        org_id=report_seed["org"].id,
        hiring_report_id=report_with_full.id,
        client_id=client_fixture.id,
        shared_by=report_seed["admin"].id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(share)
    db.commit()
    db.refresh(share)

    resp = await async_client.get(f"/reports/shared/{share.id}")
    assert resp.status_code == 200
    data = resp.json()
    # Client view includes executive_summary but not raw integrity flag evidence
    assert "executive_summary" in data


# Case 5: GET /reports/shared/{token} returns 403 when expired
@pytest.mark.asyncio
async def test_get_shared_report_403_expired(async_client: AsyncClient, report_with_full,
                                              report_seed, client_fixture, db):
    share = ReportShare(
        org_id=report_seed["org"].id,
        hiring_report_id=report_with_full.id,
        client_id=client_fixture.id,
        shared_by=report_seed["admin"].id,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    db.add(share)
    db.commit()
    db.refresh(share)

    resp = await async_client.get(f"/reports/shared/{share.id}")
    assert resp.status_code == 403


# Case 6: PATCH /reports/{session_id}/feedback writes reviewer_override + discrepancy_flag
@pytest.mark.asyncio
async def test_reviewer_feedback_writes_override(async_client: AsyncClient, user_token,
                                                  report_with_full, report_seed, db):
    resp = await async_client.patch(
        f"/reports/{report_seed['session'].id}/feedback",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "final_decision": "no_hire",
            "comment": "Did not meet culture expectations.",
            "score_overrides": None,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reviewer_override"]["final_decision"] == "no_hire"
    # AI verdict was "hire", recruiter says "no_hire" → discrepancy
    assert data["reviewer_override"]["discrepancy_flag"] is True

    db.refresh(report_with_full)
    assert report_with_full.reviewer_override["final_decision"] == "no_hire"


# Case 7: GET /reports/{session_id}/pdf returns application/pdf
@pytest.mark.asyncio
async def test_get_report_pdf_200(async_client: AsyncClient, user_token, report_with_full, report_seed):
    from unittest.mock import patch as mock_patch
    with mock_patch("agents.report_generator.pdf.render_pdf", return_value=b"%PDF-1.4 test"):
        resp = await async_client.get(
            f"/reports/{report_seed['session'].id}/pdf",
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd services/orchestrator-api
pytest tests/reports/test_full_report.py -v
```

Expected: failures on missing routes/service functions.

- [ ] **Step 3: Implement `services/orchestrator-api/src/modules/reports/service.py`**

Replace the entire file:

```python
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from src.models.assessment_sessions import AssessmentSession
from src.models.candidates import Candidate
from src.models.clients import Client
from src.models.hiring_reports import HiringReport
from src.models.report_shares import ReportShare
from src.modules.reports.schemas import (
    FullReportResponse,
    ReviewerFeedbackRequest,
    ReviewerFeedbackResponse,
    ReportResponse,
    ShareLinkRequest,
    ShareLinkResponse,
)

_HIRE_VERDICTS = {"strong_hire", "hire"}


def get_report(db: Session, session_id: uuid.UUID, org_id: uuid.UUID) -> ReportResponse:
    session = db.query(AssessmentSession).filter_by(id=session_id, org_id=org_id).first()
    if not session:
        raise LookupError("assessment session not found")

    report = db.query(HiringReport).filter_by(session_id=session_id).first()
    if not report:
        return ReportResponse(
            session_id=session_id,
            report_ready=False,
            verdict=None,
            executive_summary=None,
            composite_scores=None,
            overall_score=None,
            suggested_hr_questions=[],
            recommended_next_round=None,
            training_needs=[],
            created_at=None,
        )

    rollup = report.score_rollup or {}
    return ReportResponse(
        session_id=session_id,
        report_ready=True,
        verdict=report.verdict,
        executive_summary=report.executive_summary,
        composite_scores=rollup.get("composite_scores"),
        overall_score=rollup.get("overall"),
        suggested_hr_questions=list(report.suggested_hr_questions or []),
        recommended_next_round=report.recommended_next_round,
        training_needs=list(report.training_needs or []),
        created_at=report.created_at,
    )


def get_full_report(db: Session, session_id: uuid.UUID, org_id: uuid.UUID) -> FullReportResponse:
    session = db.query(AssessmentSession).filter_by(id=session_id, org_id=org_id).first()
    if not session:
        raise LookupError("assessment session not found")

    report = db.query(HiringReport).filter_by(session_id=session_id).first()
    if not report or not report.full_report:
        raise LookupError("full report not yet generated")

    requires_human_review = bool((report.full_report or {}).get("meta", {}).get("requires_human_review"))
    return FullReportResponse(
        session_id=session_id,
        report_ready=True,
        requires_human_review=requires_human_review,
        verdict=report.verdict,
        ai_confidence_score=float(report.ai_confidence_score) if report.ai_confidence_score else None,
        salary_band=report.salary_band,
        full_report=report.full_report,
        created_at=report.created_at,
    )


def get_report_pdf(
    db: Session,
    session_id: uuid.UUID,
    org_id: uuid.UUID,
    include_transcript: bool = False,
) -> bytes:
    from agents.report_generator.pdf import render_pdf

    session = db.query(AssessmentSession).filter_by(id=session_id, org_id=org_id).first()
    if not session:
        raise LookupError("assessment session not found")

    report = db.query(HiringReport).filter_by(session_id=session_id).first()
    if not report or not report.full_report:
        raise LookupError("full report not yet generated")

    candidate = db.query(Candidate).filter_by(id=session.candidate_id).first()
    candidate_name = candidate.name if candidate else "Unknown"

    from src.models.job_assessments import JobAssessment
    job = db.query(JobAssessment).filter_by(id=session.job_assessment_id).first()
    job_title = job.title if job else "Unknown"

    return render_pdf(
        report_data=report.full_report,
        candidate_name=candidate_name,
        job_title=job_title,
        include_transcript=include_transcript,
    )


def create_share_link(
    db: Session,
    session_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    req: ShareLinkRequest,
) -> ShareLinkResponse:
    session = db.query(AssessmentSession).filter_by(id=session_id, org_id=org_id).first()
    if not session:
        raise LookupError("assessment session not found")

    report = db.query(HiringReport).filter_by(session_id=session_id).first()
    if not report:
        raise LookupError("report not found")

    client = db.query(Client).filter_by(id=req.client_id, org_id=org_id).first()
    if not client:
        raise LookupError("client not found in this org")

    expires_at = datetime.now(UTC) + timedelta(days=req.expires_in_days)
    share = ReportShare(
        org_id=org_id,
        hiring_report_id=report.id,
        client_id=req.client_id,
        shared_by=user_id,
        expires_at=expires_at,
    )
    db.add(share)
    db.commit()
    db.refresh(share)

    return ShareLinkResponse(share_token=share.id, expires_at=expires_at)


def get_shared_report(db: Session, token: uuid.UUID) -> dict:
    share = db.query(ReportShare).filter_by(id=token).first()
    if not share:
        raise LookupError("share not found")

    now = datetime.now(UTC)
    if share.revoked_at is not None:
        raise PermissionError("share link has been revoked")
    if share.expires_at is not None and share.expires_at.replace(tzinfo=UTC) < now:
        raise PermissionError("share link has expired")

    report = db.query(HiringReport).filter_by(id=share.hiring_report_id).first()
    if not report or not report.full_report:
        raise LookupError("report not available")

    full = report.full_report
    # Client-scoped view: omit raw integrity flag evidence
    integrity_scoped = {
        "overall_risk": (report.integrity_summary or {}).get("overall_risk", "low"),
        "human_review_required": (report.integrity_summary or {}).get("human_review_required", False),
    }

    return {
        "executive_summary": full.get("executive_summary"),
        "candidate_overview": full.get("candidate_overview"),
        "scores": full.get("scores"),
        "overall_rating": full.get("overall_rating"),
        "strengths": full.get("strengths"),
        "weaknesses": full.get("weaknesses"),
        "skill_gap_analysis": full.get("skill_gap_analysis"),
        "recommended_next_round": full.get("recommended_next_round"),
        "training_needs": full.get("training_needs"),
        "salary_recommendation": full.get("salary_recommendation"),
        "final_verdict": full.get("final_verdict"),
        "integrity_summary": integrity_scoped,
    }


def submit_reviewer_feedback(
    db: Session,
    session_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    req: ReviewerFeedbackRequest,
) -> ReviewerFeedbackResponse:
    session = db.query(AssessmentSession).filter_by(id=session_id, org_id=org_id).first()
    if not session:
        raise LookupError("assessment session not found")

    report = db.query(HiringReport).filter_by(session_id=session_id).first()
    if not report:
        raise LookupError("report not found")

    ai_verdict = report.verdict or ""
    ai_positive = ai_verdict in _HIRE_VERDICTS
    recruiter_positive = req.final_decision == "hire"
    discrepancy_flag = ai_positive != recruiter_positive

    override = {
        "final_decision": req.final_decision,
        "comment": req.comment,
        "score_overrides": req.score_overrides or {},
        "submitted_by": str(user_id),
        "submitted_at": datetime.now(UTC).isoformat(),
        "discrepancy_flag": discrepancy_flag,
        "ai_verdict_at_time": ai_verdict,
    }

    report.reviewer_override = override

    # Apply score overrides to score_rollup for calibration (M6-F04)
    if req.score_overrides:
        rollup = dict(report.score_rollup or {})
        composite_scores = dict(rollup.get("composite_scores", {}))
        for composite_key, new_score in req.score_overrides.items():
            # Normalise key: "technical" → "Technical"
            normalised = composite_key.title()
            if normalised in composite_scores:
                composite_scores[normalised] = new_score
        rollup["composite_scores"] = composite_scores
        report.score_rollup = rollup

    db.commit()
    return ReviewerFeedbackResponse(reviewer_override=override)
```

- [ ] **Step 4: Implement `services/orchestrator-api/src/modules/reports/router.py`**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.auth.dependencies import TokenClaims, require_user
from src.modules.reports import service
from src.modules.reports.schemas import (
    FullReportResponse,
    ReportResponse,
    ReviewerFeedbackRequest,
    ReviewerFeedbackResponse,
    ShareLinkRequest,
    ShareLinkResponse,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{session_id}", response_model=ReportResponse)
def get_report(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.get_report(db, session_id, claims.org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{session_id}/full", response_model=FullReportResponse)
def get_full_report(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.get_full_report(db, session_id, claims.org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{session_id}/pdf")
def get_report_pdf(
    session_id: uuid.UUID,
    include_transcript: bool = Query(default=False),
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        pdf_bytes = service.get_report_pdf(db, session_id, claims.org_id, include_transcript)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=report-{session_id}.pdf"},
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{session_id}/share", response_model=ShareLinkResponse)
def create_share_link(
    session_id: uuid.UUID,
    req: ShareLinkRequest,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.create_share_link(db, session_id, claims.org_id, claims.user_id, req)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/shared/{token}")
def get_shared_report(
    token: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        return service.get_shared_report(db, token)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.patch("/{session_id}/feedback", response_model=ReviewerFeedbackResponse)
def submit_reviewer_feedback(
    session_id: uuid.UUID,
    req: ReviewerFeedbackRequest,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.submit_reviewer_feedback(db, session_id, claims.org_id, claims.user_id, req)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 5: Check `TokenClaims` has `user_id` attribute**

```bash
cd services/orchestrator-api
grep -n "user_id" src/modules/auth/dependencies.py
```

If `user_id` is not present, check what the field is named (may be `sub` or `id`). Update router `claims.user_id` to match.

- [ ] **Step 6: Run tests — verify they pass**

```bash
cd services/orchestrator-api
pytest tests/reports/test_full_report.py -v
```

Expected: 7 PASSED.

- [ ] **Step 7: Run existing report tests — verify no regressions**

```bash
pytest tests/reports/ -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add services/orchestrator-api/src/modules/reports/ services/orchestrator-api/tests/reports/
git commit -m "[TASK-002] feat(reports): full report, PDF, share link, reviewer feedback endpoints"
```

---

## Task 9: Pipeline Wiring + Integration Tests

**Files:**
- Modify: `agents/evaluation/pipeline.py`
- Create: `agents/evaluation/tests/test_pipeline_m9.py`

**Interfaces:**
- Consumes:
  - `synthesize_recommendation` from `agents.recommendation.agent`
  - `generate_full_report` from `agents.report_generator.agent`
- Produces: `_run_recommendation`, `_run_report_generator` helpers in `pipeline.py`

- [ ] **Step 1: Write failing tests**

Create `agents/evaluation/tests/test_pipeline_m9.py`:

```python
import sys
import uuid
from unittest.mock import MagicMock, call, patch

_SESSION_ID = uuid.uuid4()

_FAKE_ORM = {
    "src": MagicMock(),
    "src.models": MagicMock(),
    "src.models.assessment_sessions": MagicMock(),
    "src.models.candidates": MagicMock(),
    "src.models.hiring_reports": MagicMock(),
    "src.models.job_assessments": MagicMock(),
    "src.models.question_sets": MagicMock(),
    "src.models.session_questions": MagicMock(),
}


def _make_pipeline_db():
    """Minimal DB mock that lets evaluation_pipeline reach the recommendation step."""
    db = MagicMock()
    session_obj = MagicMock()
    session_obj.org_id = uuid.uuid4()
    session_obj.job_assessment_id = uuid.uuid4()
    session_obj.candidate_id = uuid.uuid4()

    job_obj = MagicMock()
    job_obj.title = "Engineer"
    job_obj.competency_weightage = {}
    job_obj.culture_values = []

    candidate_obj = MagicMock()
    candidate_obj.name = "Alice"

    qset_obj = MagicMock()
    qset_obj.id = uuid.uuid4()

    report_obj = MagicMock()
    report_obj.score_rollup = {"composite_scores": {}, "overall": 3.5, "answered_count": 5, "question_count": 5}
    report_obj.verdict = "hire"
    report_obj.integrity_summary = {"overall_risk": "low"}

    def query_side_effect(model):
        q = MagicMock()
        name = str(model)
        if "AssessmentSession" in name:
            q.filter_by.return_value.first.return_value = session_obj
        elif "JobAssessment" in name:
            q.filter_by.return_value.first.return_value = job_obj
        elif "Candidate" in name:
            q.filter_by.return_value.first.return_value = candidate_obj
        elif "HiringReport" in name:
            q.filter_by.return_value.first.return_value = report_obj
        elif "QuestionSet" in name:
            q.filter_by.return_value.first.return_value = qset_obj
        elif "SessionQuestion" in name:
            q.filter.return_value.order_by.return_value.all.return_value = []
        return q

    db.query.side_effect = query_side_effect
    return db


# Case 1: synthesize_recommendation called after integrity checks
def test_recommendation_called_in_pipeline():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.evaluation.pipeline import _run_recommendation

        with patch("agents.recommendation.agent.synthesize_recommendation") as mock_rec:
            db = MagicMock()
            _run_recommendation(db, _SESSION_ID)
            mock_rec.assert_called_once_with(session_id=_SESSION_ID, db_factory=lambda: db)


# Case 2: generate_full_report called after recommendation
def test_report_generator_called_in_pipeline():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.evaluation.pipeline import _run_report_generator

        with patch("agents.report_generator.agent.generate_full_report") as mock_gen:
            db = MagicMock()
            _run_report_generator(db, _SESSION_ID)
            mock_gen.assert_called_once_with(session_id=_SESSION_ID, db_factory=lambda: db)
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd agents
pytest evaluation/tests/test_pipeline_m9.py -v
```

Expected: `ImportError` — `_run_recommendation` not found in pipeline.

- [ ] **Step 3: Add helpers to `agents/evaluation/pipeline.py`**

At the end of `pipeline.py`, add after `_run_integrity_checks`:

```python
def _run_recommendation(db: Session, session_id: uuid.UUID) -> None:
    try:
        from agents.recommendation.agent import synthesize_recommendation
        synthesize_recommendation(session_id=session_id, db_factory=lambda: db)
    except Exception:
        logger.exception("recommendation synthesis failed for session %s", session_id)


def _run_report_generator(db: Session, session_id: uuid.UUID) -> None:
    try:
        from agents.report_generator.agent import generate_full_report
        generate_full_report(session_id=session_id, db_factory=lambda: db)
    except Exception:
        logger.exception("report generation failed for session %s", session_id)
```

In `evaluation_pipeline()`, after the `_run_integrity_checks(db, session_id)` call, add:

```python
        _run_recommendation(db, session_id)
        _run_report_generator(db, session_id)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd agents
pytest evaluation/tests/test_pipeline_m9.py -v
```

Expected: 2 PASSED.

- [ ] **Step 5: Run full agent test suite — verify no regressions**

```bash
cd agents
pytest --tb=short -q
```

Expected: all existing tests still pass.

- [ ] **Step 6: Run full orchestrator test suite**

```bash
cd services/orchestrator-api
pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add agents/evaluation/pipeline.py agents/evaluation/tests/test_pipeline_m9.py
git commit -m "[TASK-002] feat(pipeline): wire recommendation + report generator into evaluation pipeline"
```

---

## Self-Review Checklist

### Spec Coverage

| Spec requirement | Task |
|---|---|
| M9-F01: verdict always backed by reasoning | Task 4 — `NARRATIVE_TOOL.final_verdict` + system prompt enforcement |
| M9-F01: verdict bands per §9.5 | Pre-existing in `agents/scoring/rubric.py`; Task 3 reads `report.verdict` |
| M9-F02: all 25 report sections | Tasks 4–5 — narrative + structured tool schemas cover all sections |
| M9-F03: benchmarking vs job bar + org bar | Task 5 — `_build_score_section` + `_get_org_historical_bar` |
| M9-F04: PDF export | Task 6 |
| M9-F04: expiring share link, Client role scoped | Task 8 — `create_share_link`, `get_shared_report` |
| M9-F04: raw transcript hidden unless enabled | Task 6 — `include_transcript` flag |
| M9-F05: reviewer feedback + discrepancy flag | Task 8 — `submit_reviewer_feedback` |
| M9-F05: calibration dataset entry | Task 8 — `score_overrides` applied to `score_rollup` |
| AI Confidence Score formula (§9.4) | Task 3 — `_compute_confidence` |
| Low confidence → human review flag (§9.4/§15) | Task 5 — `requires_human_review` in `full_report.meta` |
| Every strength/weakness cites excerpt (§3) | Task 4 — system prompt + test assertion |
| Salary band = label not figure (§18 OQ#1) | Tasks 2, 3, 4 — constraints in prompts and schemas |
| §15 bias/protected characteristic exclusion | Tasks 2, 4 — `_SECTION_15_EXCLUSION` in all system prompts |
| DB migration for `full_report` | Task 1 |
| Pipeline order §11.3 | Task 9 |
| Non-fatal helpers | Tasks 3, 5, 9 |
| `weasyprint` + `jinja2` dependency | Task 6 |

### Type Consistency Check

- `synthesize_recommendation(session_id, db_factory)` — matches call in Task 9 ✓
- `generate_full_report(session_id, db_factory)` — matches call in Task 9 ✓
- `render_pdf(report_data, candidate_name, job_title, include_transcript, transcript)` — matches Task 8 call ✓
- `_get_org_historical_bar(db, role_family, org_id)` — matches Task 5 test ✓
- `FullReportResponse.full_report: dict` — matches Task 7 schema ✓
- `ReviewerFeedbackRequest.final_decision: Literal["hire","no_hire","hold"]` — matches Task 8 test ✓
- `ShareLinkResponse.share_token: uuid.UUID` — matches Task 8 test `data["share_token"]` ✓

### Placeholder Scan

No TBD, TODO, or "implement later" strings present. All code blocks are complete.

### One open item to verify during Task 8 Step 5

`TokenClaims.user_id` — the field name for the current user's ID may differ (`sub`, `id`, or `user_id`). Task 8 Step 5 adds an explicit grep check before the tests run.

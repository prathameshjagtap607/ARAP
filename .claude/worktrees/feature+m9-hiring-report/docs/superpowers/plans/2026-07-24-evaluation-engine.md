# Evaluation Engine & Basic Hiring Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After a candidate submits their test, automatically score every answer against the competency rubric, roll up composite scores, derive a verdict, and produce a basic hiring report — all within 5 minutes, without blocking the submit response.

**Architecture:** `POST /sessions/{id}/submit` returns immediately with `status=completed`; a FastAPI `BackgroundTask` runs the evaluation pipeline in three phases: per-answer LLM scoring → math roll-up → report LLM call. Results land in `session_questions.evaluation` (per-answer) and `hiring_reports` (roll-up + verdict + summary). A new `GET /reports/{session_id}` endpoint exposes the recruiter-only report.

**Tech Stack:** FastAPI BackgroundTasks, Anthropic SDK (tool-use forced call), SQLAlchemy 2.x sync, PostgreSQL JSONB, pytest with real test DB at `postgresql://arap:arap@localhost:5434/arap_test`.

## Global Constraints

- Model: `claude-sonnet-4-6` for all LLM calls (matches existing agents)
- Score scale: 1–5 integers, never floats from LLM (PRD §9.2)
- Raw competency scores: recruiter/panel only — never in candidate-facing responses
- No Alembic migration — all DB columns already exist
- Commit format: `[TASK-001] verb: what changed`
- Never score all 20 competencies for one answer — only `target_competencies` on that question
- Calibration in Phase 1 is training-data capture only; does NOT re-trigger roll-up

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Create | `agents/scoring/rubric.py` | 20-competency definitions, composite groupings, difficulty weights, verdict thresholds |
| Create | `agents/scoring/agent.py` | `roll_up()` — pure math, no LLM |
| Create | `agents/evaluation/prompts.py` | Evaluation tool schema + system prompt |
| Create | `agents/evaluation/agent.py` | `score_answer()` — one LLM call per question |
| Create | `agents/evaluation/pipeline.py` | `evaluation_pipeline()` — orchestrates phases 1–3, owns its own DB session |
| Create | `services/orchestrator-api/src/modules/reports/__init__.py` | Module marker |
| Create | `services/orchestrator-api/src/modules/reports/schemas.py` | Request/response Pydantic models |
| Create | `services/orchestrator-api/src/modules/reports/service.py` | `get_report()`, `create_report()` |
| Create | `services/orchestrator-api/src/modules/reports/router.py` | `GET /reports/{session_id}` |
| Modify | `services/orchestrator-api/src/modules/sessions/service.py` | `calibrate_answer()` + remove direct scoring from `submit_session` |
| Modify | `services/orchestrator-api/src/modules/sessions/schemas.py` | `CalibrationRequest`, `CalibrationResponse` |
| Modify | `services/orchestrator-api/src/modules/sessions/router.py` | `PATCH …/calibration`, wire BackgroundTasks into submit |
| Modify | `services/orchestrator-api/src/main.py` | Register reports router |
| Create | `agents/scoring/tests/__init__.py` | — |
| Create | `agents/scoring/tests/test_rollup.py` | Unit tests for roll-up math and verdict bands |
| Create | `agents/evaluation/tests/__init__.py` | — |
| Create | `agents/evaluation/tests/test_pipeline.py` | Integration test: pipeline end-to-end with mocked LLM |
| Create | `services/orchestrator-api/tests/reports/__init__.py` | — |
| Create | `services/orchestrator-api/tests/reports/conftest.py` | Shared fixtures for report tests |
| Create | `services/orchestrator-api/tests/reports/test_service.py` | Report service unit tests |
| Create | `services/orchestrator-api/tests/reports/test_router.py` | Router integration tests |

---

## Task 1: Rubric — competency definitions, composite map, difficulty weights, verdict bands

**Files:**
- Create: `agents/scoring/rubric.py`
- Create: `agents/scoring/tests/__init__.py`
- Create: `agents/scoring/tests/test_rollup.py` (partial — rubric constants only)

**Interfaces:**
- Produces:
  - `DIFFICULTY_WEIGHTS: dict[str, float]` — `{"easy": 1.0, "medium": 1.5, "hard": 2.0, "expert": 3.0}`
  - `COMPETENCY_TO_COMPOSITE: dict[str, str]` — maps each competency key to one of `Technical|Leadership|Communication|Behavior`
  - `COMPOSITES: list[str]` — `["Technical", "Leadership", "Communication", "Behavior"]`
  - `VERDICT_BANDS: list[tuple[float, str]]` — ordered high→low, `[(4.25, "strong_hire"), ...]`
  - `derive_verdict(overall: float) -> str`

- [ ] **Step 1: Write the failing tests for rubric constants**

File: `agents/scoring/tests/test_rollup.py`

```python
from agents.scoring.rubric import (
    COMPETENCY_TO_COMPOSITE,
    COMPOSITES,
    DIFFICULTY_WEIGHTS,
    VERDICT_BANDS,
    derive_verdict,
)


def test_difficulty_weights_keys():
    assert set(DIFFICULTY_WEIGHTS) == {"easy", "medium", "hard", "expert"}
    assert DIFFICULTY_WEIGHTS["easy"] == 1.0
    assert DIFFICULTY_WEIGHTS["expert"] == 3.0


def test_composites_list():
    assert set(COMPOSITES) == {"Technical", "Leadership", "Communication", "Behavior"}


def test_competency_to_composite_coverage():
    for comp, cat in COMPETENCY_TO_COMPOSITE.items():
        assert cat in COMPOSITES, f"{comp} maps to unknown composite {cat}"


def test_verdict_bands_coverage():
    # every verdict value must be one of the 5 PRD bands
    valid = {"strong_hire", "hire", "consider", "borderline", "reject"}
    for _, v in VERDICT_BANDS:
        assert v in valid


def test_derive_verdict_thresholds():
    assert derive_verdict(4.25) == "strong_hire"
    assert derive_verdict(4.5) == "strong_hire"
    assert derive_verdict(3.50) == "hire"
    assert derive_verdict(3.49) == "consider"
    assert derive_verdict(2.75) == "consider"
    assert derive_verdict(2.00) == "borderline"
    assert derive_verdict(1.99) == "reject"
    assert derive_verdict(0.0) == "reject"
```

- [ ] **Step 2: Run test to verify it fails**

```
cd services/orchestrator-api
pytest ../../agents/scoring/tests/test_rollup.py -v
```

Expected: `ModuleNotFoundError` or `ImportError`.

- [ ] **Step 3: Create `agents/scoring/tests/__init__.py`**

```python
```
(empty)

- [ ] **Step 4: Create `agents/scoring/rubric.py`**

```python
DIFFICULTY_WEIGHTS: dict[str, float] = {
    "easy": 1.0,
    "medium": 1.5,
    "hard": 2.0,
    "expert": 3.0,
}

COMPOSITES: list[str] = ["Technical", "Leadership", "Communication", "Behavior"]

COMPETENCY_TO_COMPOSITE: dict[str, str] = {
    "technical": "Technical",
    "problem_solving": "Technical",
    "analytical": "Technical",
    "financial": "Technical",
    "business_strategy": "Technical",
    "leadership": "Leadership",
    "decision_making": "Leadership",
    "innovation": "Leadership",
    "priority_management": "Leadership",
    "negotiation": "Leadership",
    "communication": "Communication",
    "presentation": "Communication",
    "conflict_resolution": "Communication",
    "customer_handling": "Communication",
    "ethics": "Behavior",
    "culture_fit": "Behavior",
    "stress": "Behavior",
    "situational_judgment": "Behavior",
    "behavioral": "Behavior",
}

# Ordered high → low; first threshold the overall score meets wins.
VERDICT_BANDS: list[tuple[float, str]] = [
    (4.25, "strong_hire"),
    (3.50, "hire"),
    (2.75, "consider"),
    (2.00, "borderline"),
]


def derive_verdict(overall: float) -> str:
    for threshold, verdict in VERDICT_BANDS:
        if overall >= threshold:
            return verdict
    return "reject"
```

- [ ] **Step 5: Run tests**

```
cd services/orchestrator-api
pytest ../../agents/scoring/tests/test_rollup.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```
git add agents/scoring/rubric.py agents/scoring/tests/__init__.py agents/scoring/tests/test_rollup.py
git commit -m "[TASK-001] feat: add scoring rubric — competency map, difficulty weights, verdict bands"
```

---

## Task 2: Scoring Agent — roll-up math (M6-F03)

**Files:**
- Create: `agents/scoring/agent.py`
- Modify: `agents/scoring/tests/test_rollup.py` (add roll-up tests)

**Interfaces:**
- Consumes: `DIFFICULTY_WEIGHTS`, `COMPETENCY_TO_COMPOSITE` from `agents.scoring.rubric`
- Produces: `roll_up(answered_questions: list[dict], job_weightage: dict[str, float]) -> dict`
  - `answered_questions`: each item has `{"target_competencies": [...], "difficulty": str, "evaluation": {"competency_scores": [{"competency": str, "score": int}]}}`
  - Returns `{"competency_scores": dict, "composite_scores": dict, "overall": float, "question_count": int, "answered_count": int}`

- [ ] **Step 1: Add roll-up tests to `agents/scoring/tests/test_rollup.py`**

Append to the existing file:

```python
from agents.scoring.agent import roll_up


def _make_q(competency: str, score: int, difficulty: str = "medium") -> dict:
    return {
        "target_competencies": [competency],
        "difficulty": difficulty,
        "evaluation": {
            "competency_scores": [{"competency": competency, "score": score}]
        },
    }


def test_rollup_single_question():
    questions = [_make_q("problem_solving", 4, "medium")]
    result = roll_up(questions, job_weightage={"problem_solving": 100.0})
    assert result["competency_scores"]["problem_solving"] == pytest.approx(4.0)
    assert result["composite_scores"]["Technical"] == pytest.approx(4.0)
    assert result["overall"] == pytest.approx(4.0)
    assert result["question_count"] == 1
    assert result["answered_count"] == 1


def test_rollup_difficulty_weighting():
    # easy score=2, hard score=4 → weighted: (2*1.0 + 4*2.0)/(1.0+2.0) = 10/3 ≈ 3.333
    questions = [
        _make_q("problem_solving", 2, "easy"),
        _make_q("problem_solving", 4, "hard"),
    ]
    result = roll_up(questions, job_weightage={"problem_solving": 100.0})
    assert result["competency_scores"]["problem_solving"] == pytest.approx(10 / 3, rel=1e-3)


def test_rollup_skips_unevaluated():
    # question with no evaluation key is not counted
    q_unevaluated = {"target_competencies": ["communication"], "difficulty": "easy", "evaluation": None}
    questions = [_make_q("problem_solving", 3), q_unevaluated]
    result = roll_up(questions, job_weightage={"problem_solving": 50.0, "communication": 50.0})
    assert "communication" not in result["competency_scores"]
    assert result["answered_count"] == 1


def test_rollup_overall_is_mean_of_composites():
    # Two composites, each with one competency
    questions = [
        _make_q("problem_solving", 4),   # Technical
        _make_q("communication", 2),      # Communication
    ]
    result = roll_up(questions, job_weightage={"problem_solving": 50.0, "communication": 50.0})
    expected_overall = (result["composite_scores"]["Technical"] + result["composite_scores"]["Communication"]) / 2
    assert result["overall"] == pytest.approx(expected_overall, rel=1e-3)


def test_rollup_empty_questions():
    result = roll_up([], job_weightage={})
    assert result["overall"] == 0.0
    assert result["competency_scores"] == {}
    assert result["composite_scores"] == {}
```

Add `import pytest` at top of file.

- [ ] **Step 2: Run to verify fails**

```
cd services/orchestrator-api
pytest ../../agents/scoring/tests/test_rollup.py::test_rollup_single_question -v
```

Expected: `ImportError: cannot import name 'roll_up'`

- [ ] **Step 3: Create `agents/scoring/agent.py`**

```python
import logging

from agents.scoring.rubric import (
    COMPETENCY_TO_COMPOSITE,
    COMPOSITES,
    DIFFICULTY_WEIGHTS,
)

logger = logging.getLogger(__name__)


def roll_up(answered_questions: list[dict], job_weightage: dict[str, float]) -> dict:
    """
    Compute per-competency weighted scores and 4 composite scores from evaluated questions.
    answered_questions: each must have 'target_competencies', 'difficulty', 'evaluation'.
    job_weightage: competency key → weight (from job_assessments.competency_weightage).
    """
    # Accumulate weighted scores per competency: {competency: (sum_weighted, sum_weights)}
    accum: dict[str, list[float]] = {}  # competency → [sum_weighted_scores, sum_weights]
    answered_count = 0

    for q in answered_questions:
        evaluation = q.get("evaluation")
        if not evaluation or "competency_scores" not in evaluation:
            continue
        answered_count += 1
        diff = q.get("difficulty", "medium")
        w = DIFFICULTY_WEIGHTS.get(diff, 1.5)
        for cs in evaluation["competency_scores"]:
            comp = cs.get("competency")
            score = cs.get("score")
            if comp is None or score is None:
                continue
            if comp not in accum:
                accum[comp] = [0.0, 0.0]
            accum[comp][0] += score * w
            accum[comp][1] += w

    competency_scores: dict[str, float] = {
        comp: vals[0] / vals[1]
        for comp, vals in accum.items()
        if vals[1] > 0
    }

    # Composite scores: weighted average of constituent competencies using job_weightage
    composite_accum: dict[str, list[float]] = {c: [0.0, 0.0] for c in COMPOSITES}
    for comp, score in competency_scores.items():
        cat = COMPETENCY_TO_COMPOSITE.get(comp)
        if cat is None:
            logger.warning("competency %r not in rubric — skipped in composite", comp)
            continue
        jw = job_weightage.get(comp, 1.0)
        composite_accum[cat][0] += score * jw
        composite_accum[cat][1] += jw

    composite_scores: dict[str, float] = {
        cat: vals[0] / vals[1]
        for cat, vals in composite_accum.items()
        if vals[1] > 0
    }

    overall = (
        sum(composite_scores.values()) / len(composite_scores)
        if composite_scores
        else 0.0
    )

    return {
        "competency_scores": competency_scores,
        "composite_scores": composite_scores,
        "overall": round(overall, 4),
        "question_count": len(answered_questions),
        "answered_count": answered_count,
    }
```

- [ ] **Step 4: Run all roll-up tests**

```
cd services/orchestrator-api
pytest ../../agents/scoring/tests/test_rollup.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```
git add agents/scoring/agent.py agents/scoring/tests/test_rollup.py
git commit -m "[TASK-001] feat: add scoring agent roll-up with difficulty and job-weightage math"
```

---

## Task 3: Evaluation Agent — LLM scoring per answer (M6-F01, F02)

**Files:**
- Create: `agents/evaluation/prompts.py`
- Create: `agents/evaluation/agent.py`
- Create: `agents/evaluation/tests/__init__.py`
- Create: `agents/evaluation/tests/test_pipeline.py` (evaluation agent unit tests only in this task)

**Interfaces:**
- Produces: `score_answer(question_text: str, category: str, target_competencies: list[str], answer_text: str | None, difficulty: str, job_title: str) -> dict`
  - Returns `{"competency_scores": [{"competency": str, "score": int, "explanation": str, "evidence_quote": str, "strength": str, "improvement": str}]}`
  - On blank/None answer: returns the no-answer fallback without calling LLM
  - On LLM failure: returns `{"error": "evaluation_failed"}`

- [ ] **Step 1: Write failing tests**

File: `agents/evaluation/tests/test_pipeline.py`

```python
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
```

- [ ] **Step 2: Run to verify fails**

```
cd services/orchestrator-api
pytest ../../agents/evaluation/tests/test_pipeline.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `agents/evaluation/tests/__init__.py`**

```python
```
(empty)

- [ ] **Step 4: Create `agents/evaluation/prompts.py`**

```python
PROMPT_VERSION = "v1.0"

SYSTEM_PROMPT = (
    "You are the Evaluation Agent for a structured recruitment assessment. "
    "Score only the competencies listed in target_competencies — never others. "
    "Use the 1-5 scale: 1=no evidence, 2=partial/weak, 3=adequate, 4=strong, 5=exceptional. "
    "For evidence_quote, copy an exact verbatim excerpt from the candidate's answer. "
    "Be concise and specific."
)


def build_evaluation_tool(target_competencies: list[str]) -> dict:
    return {
        "name": "evaluate_answer",
        "description": "Score the candidate answer against the specified competencies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "competency_scores": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "competency": {
                                "type": "string",
                                "enum": target_competencies,
                            },
                            "score": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 5,
                            },
                            "explanation": {"type": "string"},
                            "evidence_quote": {
                                "type": "string",
                                "description": "Verbatim excerpt from the candidate's answer.",
                            },
                            "strength": {"type": "string"},
                            "improvement": {"type": "string"},
                        },
                        "required": [
                            "competency", "score", "explanation",
                            "evidence_quote", "strength", "improvement",
                        ],
                    },
                    "minItems": len(target_competencies),
                    "maxItems": len(target_competencies),
                }
            },
            "required": ["competency_scores"],
        },
    }
```

- [ ] **Step 5: Create `agents/evaluation/agent.py`**

```python
import logging

import anthropic

from agents.evaluation.prompts import SYSTEM_PROMPT, build_evaluation_tool

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096


def _no_answer_fallback(target_competencies: list[str]) -> dict:
    return {
        "competency_scores": [
            {
                "competency": comp,
                "score": 1,
                "explanation": "No answer provided.",
                "evidence_quote": "",
                "strength": "N/A",
                "improvement": "Candidate did not respond to this question.",
            }
            for comp in target_competencies
        ]
    }


def score_answer(
    question_text: str,
    category: str,
    target_competencies: list[str],
    answer_text: str | None,
    difficulty: str,
    job_title: str,
) -> dict:
    if not answer_text or not answer_text.strip():
        return _no_answer_fallback(target_competencies)

    user_message = "\n".join([
        f"job_title: {job_title}",
        f"question_category: {category}",
        f"question_difficulty: {difficulty}",
        f"target_competencies: {target_competencies}",
        "",
        f"QUESTION:\n{question_text}",
        "",
        f"CANDIDATE ANSWER:\n{answer_text}",
    ])

    try:
        client = anthropic.Anthropic()
        tool = build_evaluation_tool(target_competencies)
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[tool],
            tool_choice={"type": "tool", "name": "evaluate_answer"},
            messages=[{"role": "user", "content": user_message}],
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        return {"competency_scores": list(tool_block.input["competency_scores"])}
    except Exception:
        logger.exception("Evaluation agent failed for question — returning error sentinel")
        return {"error": "evaluation_failed"}
```

- [ ] **Step 6: Run tests**

```
cd services/orchestrator-api
pytest ../../agents/evaluation/tests/test_pipeline.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 7: Commit**

```
git add agents/evaluation/prompts.py agents/evaluation/agent.py agents/evaluation/tests/__init__.py agents/evaluation/tests/test_pipeline.py
git commit -m "[TASK-001] feat: add evaluation agent — LLM per-answer scoring with evidence and fallbacks"
```

---

## Task 4: Evaluation Pipeline — orchestration + submit trigger (M6-F01 → F03)

**Files:**
- Create: `agents/evaluation/pipeline.py`
- Modify: `services/orchestrator-api/src/modules/sessions/service.py`
- Modify: `services/orchestrator-api/src/modules/sessions/router.py`
- Modify: `agents/evaluation/tests/test_pipeline.py` (add pipeline integration test)

**Interfaces:**
- Consumes:
  - `score_answer(...)` from `agents.evaluation.agent`
  - `roll_up(answered_questions, job_weightage)` from `agents.scoring.agent`
  - `derive_verdict(overall)` from `agents.scoring.rubric`
  - `SessionLocal` from `src.database` (background task owns its own session)
- Produces: `evaluation_pipeline(session_id: uuid.UUID, db_factory: Callable[[], Session]) -> None`
  - Writes `session_questions.evaluation` for each question
  - Writes `hiring_reports` row (score_rollup + verdict; executive_summary is filled by Task 6)

- [ ] **Step 1: Add pipeline integration test**

Append to `agents/evaluation/tests/test_pipeline.py`:

```python
import uuid
from unittest.mock import MagicMock, call, patch

from agents.evaluation.pipeline import evaluation_pipeline


def _make_session_question(comp: str = "problem_solving", answer: str = "My answer") -> MagicMock:
    q = MagicMock()
    q.id = uuid.uuid4()
    q.question = {"text": "Describe your approach."}
    q.category = "Technical"
    q.target_competencies = [comp]
    q.difficulty = "medium"
    q.answer_text = answer
    q.evaluation = None
    return q


def test_evaluation_pipeline_scores_and_writes_report():
    session_id = uuid.uuid4()
    org_id = uuid.uuid4()

    mock_session = MagicMock()
    mock_session.org_id = org_id
    mock_session.job_assessment_id = uuid.uuid4()

    mock_job = MagicMock()
    mock_job.title = "Senior Engineer"
    mock_job.competency_weightage = {"problem_solving": 100.0}

    mock_qset = MagicMock()
    mock_qset.id = uuid.uuid4()

    q1 = _make_session_question("problem_solving", "I approach problems systematically.")
    q2 = _make_session_question("problem_solving", None)  # unanswered

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        mock_session, mock_job, mock_qset,
    ]
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [q1, q2]
    mock_db.query.return_value.filter_by.return_value.first.return_value = None  # report not yet

    fake_eval = {
        "competency_scores": [{
            "competency": "problem_solving",
            "score": 4,
            "explanation": "Good",
            "evidence_quote": "I approach",
            "strength": "Systematic",
            "improvement": "Be more concise",
        }]
    }

    with patch("agents.evaluation.pipeline.score_answer", return_value=fake_eval) as mock_score, \
         patch("agents.evaluation.pipeline.roll_up", return_value={
             "competency_scores": {"problem_solving": 3.5},
             "composite_scores": {"Technical": 3.5},
             "overall": 3.5,
             "question_count": 2,
             "answered_count": 1,
         }) as mock_rollup, \
         patch("agents.evaluation.pipeline.derive_verdict", return_value="hire") as mock_verdict:

        db_factory = MagicMock(return_value=mock_db)
        evaluation_pipeline(session_id, db_factory)

    mock_score.assert_called()
    mock_rollup.assert_called_once()
    mock_verdict.assert_called_once_with(3.5)
    mock_db.add.assert_called()  # HiringReport added
    mock_db.commit.assert_called()
```

- [ ] **Step 2: Run to verify fails**

```
cd services/orchestrator-api
pytest ../../agents/evaluation/tests/test_pipeline.py::test_evaluation_pipeline_scores_and_writes_report -v
```

Expected: `ImportError: cannot import name 'evaluation_pipeline'`

- [ ] **Step 3: Create `agents/evaluation/pipeline.py`**

```python
import logging
import uuid
from typing import Callable

from sqlalchemy.orm import Session

from agents.evaluation.agent import score_answer
from agents.scoring.agent import roll_up
from agents.scoring.rubric import derive_verdict

logger = logging.getLogger(__name__)


def evaluation_pipeline(session_id: uuid.UUID, db_factory: Callable[[], Session]) -> None:
    """
    Runs after submit_session completes. Owns its own DB session (not request-scoped).
    Phase 1: Score each answered question via LLM.
    Phase 2: Roll up competency scores.
    Phase 3: Write hiring_reports row.
    """
    # Import here to avoid circular imports at module load time
    from src.models.assessment_sessions import AssessmentSession
    from src.models.hiring_reports import HiringReport
    from src.models.job_assessments import JobAssessment
    from src.models.question_sets import QuestionSet
    from src.models.session_questions import SessionQuestion

    db = db_factory()
    try:
        session = db.query(AssessmentSession).filter_by(id=session_id).first()
        if not session:
            logger.error("evaluation_pipeline: session %s not found", session_id)
            return

        job = db.query(JobAssessment).filter_by(id=session.job_assessment_id).first()
        job_title = job.title if job else ""
        job_weightage = dict(job.competency_weightage) if job else {}

        qset = db.query(QuestionSet).filter_by(session_id=session_id).first()
        if not qset:
            logger.error("evaluation_pipeline: question set not found for session %s", session_id)
            return

        questions = (
            db.query(SessionQuestion)
            .filter(SessionQuestion.question_set_id == qset.id)
            .order_by(SessionQuestion.sequence_no)
            .all()
        )

        # Phase 1 — score each question
        evaluated: list[dict] = []
        for q in questions:
            eval_result = score_answer(
                question_text=q.question.get("text", ""),
                category=q.category,
                target_competencies=list(q.target_competencies),
                answer_text=q.answer_text,
                difficulty=q.difficulty,
                job_title=job_title,
            )
            q.evaluation = eval_result
            db.flush()
            evaluated.append({
                "target_competencies": list(q.target_competencies),
                "difficulty": q.difficulty,
                "evaluation": eval_result if "error" not in eval_result else None,
            })

        db.commit()
        logger.info("evaluation_pipeline: scored %d questions for session %s", len(questions), session_id)

        # Phase 2 — roll up
        rollup = roll_up(evaluated, job_weightage)
        verdict = derive_verdict(rollup["overall"])

        # Phase 3 — write report (exec summary added by report_service later)
        existing_report = db.query(HiringReport).filter_by(session_id=session_id).first()
        if existing_report:
            existing_report.score_rollup = rollup
            existing_report.verdict = verdict
        else:
            report = HiringReport(
                org_id=session.org_id,
                session_id=session_id,
                score_rollup=rollup,
                verdict=verdict,
                executive_summary=None,
            )
            db.add(report)

        db.commit()
        logger.info(
            "evaluation_pipeline: report written session=%s verdict=%s overall=%.2f",
            session_id, verdict, rollup["overall"],
        )

        # Generate executive summary (separate LLM call)
        _generate_executive_summary(db, session_id, job_title, rollup, verdict)

    except Exception:
        logger.exception("evaluation_pipeline failed for session %s", session_id)
        db.rollback()
    finally:
        db.close()


def _generate_executive_summary(
    db: Session,
    session_id: uuid.UUID,
    job_title: str,
    rollup: dict,
    verdict: str,
) -> None:
    from src.models.hiring_reports import HiringReport
    from agents.evaluation.summary import generate_summary

    result = generate_summary(job_title=job_title, rollup=rollup, verdict=verdict)
    report = db.query(HiringReport).filter_by(session_id=session_id).first()
    if report and result:
        report.executive_summary = result.get("executive_summary")
        report.suggested_hr_questions = result.get("suggested_hr_questions", [])
        report.recommended_next_round = result.get("recommended_next_round")
        report.training_needs = result.get("training_needs", [])
        db.commit()
```

- [ ] **Step 4: Modify `services/orchestrator-api/src/modules/sessions/service.py`**

Add `calibrate_answer` function and update `submit_session` signature to accept a `run_pipeline` callable:

At the top of the file add import:
```python
import uuid
```
(already present — skip if already imported)

Replace the `submit_session` function with:

```python
def submit_session(
    db: Session,
    session_id: uuid.UUID,
    org_id: uuid.UUID,
    on_complete: Callable | None = None,
) -> SubmitResponse:
    session = _get_session_or_404(db, session_id, org_id)
    if session.status == "in_progress":
        pass
    elif session.status in ("completed", "expired"):
        return SubmitResponse(status=session.status, completed_at=session.completed_at)
    else:
        raise ValueError(f"session must be in_progress to submit (is {session.status})")

    now = datetime.now(UTC)
    has_answers = (
        db.query(SessionQuestion)
        .join(QuestionSet, SessionQuestion.question_set_id == QuestionSet.id)
        .filter(QuestionSet.session_id == session_id, SessionQuestion.answered_at.isnot(None))
        .count()
    ) > 0

    expired = _seconds_remaining(session) == 0

    if expired and not has_answers:
        session.status = "expired"
    else:
        session.status = "completed"
        session.completed_at = now

    db.flush()
    db.commit()
    logger.info("session %s submitted status=%s", session_id, session.status)

    if session.status == "completed" and on_complete is not None:
        on_complete()

    return SubmitResponse(status=session.status, completed_at=session.completed_at)
```

Add this import at the top of the file (after existing imports):
```python
from collections.abc import Callable
```

Also add `calibrate_answer` at the end of `service.py`:

```python
def calibrate_answer(
    db: Session,
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    org_id: uuid.UUID,
    override_score: int,
    comment: str,
    reviewer_id: uuid.UUID,
) -> dict:
    from datetime import UTC, datetime

    from src.models.hiring_reports import HiringReport

    session = _get_session_or_404(db, session_id, org_id)

    q = (
        db.query(SessionQuestion)
        .join(QuestionSet, SessionQuestion.question_set_id == QuestionSet.id)
        .filter(
            SessionQuestion.id == question_id,
            QuestionSet.session_id == session_id,
        )
        .first()
    )
    if not q:
        raise LookupError("question not found")

    calibration = {
        "override_score": override_score,
        "comment": comment,
        "overridden_by": str(reviewer_id),
        "overridden_at": datetime.now(UTC).isoformat(),
    }
    current_eval = dict(q.evaluation) if q.evaluation else {}
    current_eval["calibration"] = calibration
    q.evaluation = current_eval
    db.flush()

    # Append to hiring_reports.reviewer_override for labeled training data (M6-F04)
    report = db.query(HiringReport).filter_by(session_id=session_id).first()
    if report:
        overrides = list(report.reviewer_override or [])
        overrides.append({"question_id": str(question_id), **calibration})
        report.reviewer_override = overrides

    db.commit()
    return calibration
```

- [ ] **Step 5: Modify `services/orchestrator-api/src/modules/sessions/router.py`**

Replace the `submit` endpoint and add the `calibration` endpoint:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

# ... existing imports stay ...

from src.database import SessionLocal
from agents.evaluation.pipeline import evaluation_pipeline
from src.modules.sessions.schemas import (
    AnswerRequest,
    AnswerResponse,
    CalibrationRequest,
    CalibrationResponse,
    InviteResponse,
    SessionStateResponse,
    SubmitResponse,
)
```

Replace the `submit` function:

```python
@router.post("/{session_id}/submit", response_model=SubmitResponse)
def submit(
    session_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    claims: TokenClaims = Depends(require_candidate_scope),
    db: Session = Depends(get_db),
):
    try:
        def _run_pipeline():
            background_tasks.add_task(evaluation_pipeline, session_id, SessionLocal)

        return service.submit_session(db, session_id, claims.org_id, on_complete=_run_pipeline)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.patch(
    "/{session_id}/questions/{question_id}/calibration",
    response_model=CalibrationResponse,
)
def calibrate(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    body: CalibrationRequest,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        result = service.calibrate_answer(
            db, session_id, question_id, claims.org_id,
            body.override_score, body.comment, claims.sub,
        )
        return CalibrationResponse(**result)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

Note: `claims.sub` is a `str` (UUID as string) — cast to uuid in `calibrate_answer` if needed, or keep as str.

Update `calibrate_answer` signature to accept `reviewer_id: str` instead of `uuid.UUID`:

In `service.py`, change the parameter: `reviewer_id: str` (already serialized as str in the token).

- [ ] **Step 6: Add `CalibrationRequest` and `CalibrationResponse` to `sessions/schemas.py`**

Append to `services/orchestrator-api/src/modules/sessions/schemas.py`:

```python
class CalibrationRequest(BaseModel):
    override_score: int
    comment: str


class CalibrationResponse(BaseModel):
    override_score: int
    comment: str
    overridden_by: str
    overridden_at: str
```

- [ ] **Step 7: Run pipeline test**

```
cd services/orchestrator-api
pytest ../../agents/evaluation/tests/test_pipeline.py -v
```

Expected: all tests PASS (the new integration test may need the imports adjusted — ensure `src` is on the path via the existing conftest).

- [ ] **Step 8: Run existing session service tests to confirm no regression**

```
cd services/orchestrator-api
pytest tests/sessions/test_service.py -v
```

Expected: all existing tests PASS. (The `on_complete` default of `None` keeps the old call sites working.)

- [ ] **Step 9: Commit**

```
git add agents/evaluation/pipeline.py \
        services/orchestrator-api/src/modules/sessions/service.py \
        services/orchestrator-api/src/modules/sessions/schemas.py \
        services/orchestrator-api/src/modules/sessions/router.py
git commit -m "[TASK-001] feat: evaluation pipeline — submit triggers background scoring, add calibration endpoint"
```

---

## Task 5: Executive Summary Agent (M9-F01)

**Files:**
- Create: `agents/evaluation/summary.py`
- Modify: `agents/evaluation/tests/test_pipeline.py` (add summary unit test)

**Interfaces:**
- Produces: `generate_summary(job_title: str, rollup: dict, verdict: str) -> dict | None`
  - Returns `{"executive_summary": str, "suggested_hr_questions": list[str], "recommended_next_round": str, "training_needs": list[str]}`
  - On failure: returns `None`

- [ ] **Step 1: Add summary test**

Append to `agents/evaluation/tests/test_pipeline.py`:

```python
from agents.evaluation.summary import generate_summary


def test_generate_summary_calls_llm_and_returns_dict():
    rollup = {
        "composite_scores": {"Technical": 3.8, "Leadership": 4.0, "Communication": 3.2, "Behavior": 3.5},
        "overall": 3.625,
    }
    fake_output = {
        "executive_summary": "Candidate shows strong technical skills.",
        "suggested_hr_questions": ["Q1", "Q2", "Q3"],
        "recommended_next_round": "Technical Panel",
        "training_needs": ["Communication clarity"],
    }
    block = MagicMock()
    block.type = "tool_use"
    block.input = fake_output
    response = MagicMock()
    response.content = [block]

    with patch("agents.evaluation.summary.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = response
        result = generate_summary("Senior Engineer", rollup, "hire")

    assert result["executive_summary"] == "Candidate shows strong technical skills."
    assert len(result["suggested_hr_questions"]) == 3


def test_generate_summary_returns_none_on_failure():
    with patch("agents.evaluation.summary.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = RuntimeError("fail")
        result = generate_summary("Engineer", {}, "reject")
    assert result is None
```

- [ ] **Step 2: Run to verify fails**

```
cd services/orchestrator-api
pytest ../../agents/evaluation/tests/test_pipeline.py::test_generate_summary_calls_llm_and_returns_dict -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `agents/evaluation/summary.py`**

```python
import logging

import anthropic

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 2048

_SUMMARY_TOOL = {
    "name": "generate_report_summary",
    "description": "Generate the executive summary and supporting report fields for a hiring report.",
    "input_schema": {
        "type": "object",
        "properties": {
            "executive_summary": {
                "type": "string",
                "description": "2-3 sentence plain-English summary of the candidate's performance.",
            },
            "suggested_hr_questions": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 3,
                "description": "3 follow-up questions based on weak competencies.",
            },
            "recommended_next_round": {
                "type": "string",
                "description": "E.g. 'Technical Panel Interview' or 'Final HR Round'.",
            },
            "training_needs": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 3,
                "description": "Top 1-3 competency gaps to address if hired.",
            },
        },
        "required": [
            "executive_summary",
            "suggested_hr_questions",
            "recommended_next_round",
            "training_needs",
        ],
    },
}

_SYSTEM_PROMPT = (
    "You are a senior HR analyst writing a concise hiring recommendation. "
    "Base everything on the score data provided. Be specific and objective. "
    "Do not invent information not present in the scores."
)


def generate_summary(job_title: str, rollup: dict, verdict: str) -> dict | None:
    composite_scores = rollup.get("composite_scores", {})
    overall = rollup.get("overall", 0.0)

    user_message = "\n".join([
        f"Role: {job_title}",
        f"Verdict: {verdict}",
        f"Overall score: {overall:.2f} / 5.0",
        "Composite scores:",
        *[f"  {k}: {v:.2f}" for k, v in composite_scores.items()],
    ])

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            tools=[_SUMMARY_TOOL],
            tool_choice={"type": "tool", "name": "generate_report_summary"},
            messages=[{"role": "user", "content": user_message}],
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        return dict(tool_block.input)
    except Exception:
        logger.exception("Summary generation failed")
        return None
```

- [ ] **Step 4: Run summary tests**

```
cd services/orchestrator-api
pytest ../../agents/evaluation/tests/test_pipeline.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```
git add agents/evaluation/summary.py agents/evaluation/tests/test_pipeline.py
git commit -m "[TASK-001] feat: executive summary agent — LLM call for report narrative and HR follow-up questions"
```

---

## Task 6: Reports Module (M9-F01, F02)

**Files:**
- Create: `services/orchestrator-api/src/modules/reports/__init__.py`
- Create: `services/orchestrator-api/src/modules/reports/schemas.py`
- Create: `services/orchestrator-api/src/modules/reports/service.py`
- Create: `services/orchestrator-api/src/modules/reports/router.py`
- Modify: `services/orchestrator-api/src/main.py`
- Create: `services/orchestrator-api/tests/reports/__init__.py`
- Create: `services/orchestrator-api/tests/reports/conftest.py`
- Create: `services/orchestrator-api/tests/reports/test_service.py`
- Create: `services/orchestrator-api/tests/reports/test_router.py`

**Interfaces:**
- Produces: `GET /reports/{session_id}` → `ReportResponse`
- `ReportResponse` fields: `session_id`, `verdict`, `executive_summary`, `composite_scores`, `overall_score`, `suggested_hr_questions`, `recommended_next_round`, `training_needs`, `report_ready`, `created_at`

- [ ] **Step 1: Write failing service test**

File: `services/orchestrator-api/tests/reports/test_service.py`

```python
import pytest
from src.modules.reports import service as report_service


def test_get_report_returns_not_ready_when_no_row(db, report_seed):
    result = report_service.get_report(db, report_seed["session"].id, report_seed["org"].id)
    assert result.report_ready is False
    assert result.verdict is None


def test_get_report_returns_report_when_row_exists(db, report_seed):
    from src.models.hiring_reports import HiringReport
    report = HiringReport(
        org_id=report_seed["org"].id,
        session_id=report_seed["session"].id,
        score_rollup={
            "composite_scores": {"Technical": 3.8},
            "overall": 3.8,
        },
        verdict="hire",
        executive_summary="Strong candidate.",
    )
    db.add(report)
    db.commit()

    result = report_service.get_report(db, report_seed["session"].id, report_seed["org"].id)
    assert result.report_ready is True
    assert result.verdict == "hire"
    assert result.executive_summary == "Strong candidate."
    assert result.overall_score == pytest.approx(3.8)
```

- [ ] **Step 2: Run to verify fails**

```
cd services/orchestrator-api
pytest tests/reports/test_service.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `tests/reports/__init__.py`**

```python
```
(empty)

- [ ] **Step 4: Create `tests/reports/conftest.py`**

```python
import os
import uuid as _uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

import src.models  # noqa: F401
from src.models.assessment_sessions import AssessmentSession
from src.models.base import Base
from src.models.candidates import Candidate
from src.models.job_assessments import JobAssessment
from src.models.orgs import Org
from src.models.question_sets import QuestionSet
from src.models.users import User
from src.modules.auth.token import create_access_token

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://arap:arap@localhost:5434/arap_test"
)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL)
    with eng.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    _Session = sessionmaker(engine)
    s = _Session()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def report_seed(db: Session) -> dict:
    uid = _uuid.uuid4().hex[:8]
    org = Org(name=f"Report Test Org {uid}")
    db.add(org)
    db.flush()

    admin = User(
        org_id=org.id,
        email=f"admin-{uid}@test.com",
        role="admin",
        password_hash="x",
    )
    db.add(admin)
    db.flush()

    candidate = Candidate(
        org_id=org.id,
        name="Bob",
        email=f"bob-{uid}@example.com",
        auth_method="magic_link",
    )
    db.add(candidate)
    db.flush()

    job = JobAssessment(
        org_id=org.id,
        title="Product Manager",
        difficulty_level="mid",
        duration_minutes=45,
        competency_weightage={"problem_solving": 50.0, "communication": 50.0},
        created_by=admin.id,
    )
    db.add(job)
    db.flush()

    session = AssessmentSession(
        org_id=org.id,
        job_assessment_id=job.id,
        candidate_id=candidate.id,
        time_budget_seconds=2700,
        status="completed",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    db.add(session)
    db.flush()
    db.commit()

    db.refresh(org); db.refresh(admin); db.refresh(session)

    return {"org": org, "admin": admin, "candidate": candidate, "job": job, "session": session}


@pytest.fixture
def user_token(report_seed: dict) -> str:
    return create_access_token({
        "sub": str(report_seed["admin"].id),
        "role": "admin",
        "org_id": str(report_seed["org"].id),
    })


@pytest_asyncio.fixture
async def async_client(db: Session):
    from src.main import app
    from src.database import get_db
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 5: Create `src/modules/reports/__init__.py`**

```python
```
(empty)

- [ ] **Step 6: Create `src/modules/reports/schemas.py`**

```python
import uuid
from datetime import datetime

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
```

- [ ] **Step 7: Create `src/modules/reports/service.py`**

```python
import uuid

from sqlalchemy.orm import Session

from src.models.assessment_sessions import AssessmentSession
from src.models.hiring_reports import HiringReport
from src.modules.reports.schemas import ReportResponse

_EMPTY_REPORT = ReportResponse(
    session_id=uuid.UUID(int=0),  # placeholder, overridden below
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
```

- [ ] **Step 8: Create `src/modules/reports/router.py`**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.auth.dependencies import TokenClaims, require_user
from src.modules.reports import service
from src.modules.reports.schemas import ReportResponse

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
```

- [ ] **Step 9: Register the router in `src/main.py`**

Add after the existing `include_router(sessions_router)` line:

```python
from src.modules.reports.router import router as reports_router
# ...
app.include_router(reports_router)
```

- [ ] **Step 10: Write router test**

File: `services/orchestrator-api/tests/reports/test_router.py`

```python
import pytest


@pytest.mark.anyio
async def test_get_report_not_ready(async_client, report_seed, user_token):
    resp = await async_client.get(
        f"/reports/{report_seed['session'].id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_ready"] is False
    assert data["verdict"] is None


@pytest.mark.anyio
async def test_get_report_returns_data(async_client, report_seed, user_token, db):
    from src.models.hiring_reports import HiringReport
    report = HiringReport(
        org_id=report_seed["org"].id,
        session_id=report_seed["session"].id,
        score_rollup={"composite_scores": {"Technical": 4.0}, "overall": 4.0},
        verdict="hire",
        executive_summary="Excellent candidate.",
    )
    db.add(report)
    db.commit()

    resp = await async_client.get(
        f"/reports/{report_seed['session'].id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_ready"] is True
    assert data["verdict"] == "hire"
    assert data["overall_score"] == pytest.approx(4.0)


@pytest.mark.anyio
async def test_get_report_requires_auth(async_client, report_seed):
    resp = await async_client.get(f"/reports/{report_seed['session'].id}")
    assert resp.status_code == 401
```

- [ ] **Step 11: Run all report tests**

```
cd services/orchestrator-api
pytest tests/reports/ -v
```

Expected: all tests PASS.

- [ ] **Step 12: Run full suite to check for regressions**

```
cd services/orchestrator-api
pytest tests/ ../../agents/scoring/tests/ ../../agents/evaluation/tests/ -v --tb=short
```

Expected: all tests PASS.

- [ ] **Step 13: Commit**

```
git add services/orchestrator-api/src/modules/reports/ \
        services/orchestrator-api/src/main.py \
        services/orchestrator-api/tests/reports/
git commit -m "[TASK-001] feat: reports module — GET /reports/{session_id} with report_ready flag (M9-F01/F02)"
```

---

## Self-Review Checklist

**Spec coverage:**
- M6-F01 Batch scoring: Task 3 (evaluation agent) + Task 4 (pipeline scores all questions) ✓
- M6-F02 Explanation + evidence + strength + improvement: Task 3 tool schema enforces all 4 fields ✓
- M6-F03 Session roll-up + 4 composites: Task 2 (scoring agent) ✓
- M6-F04 Calibration capture: Task 4 (`calibrate_answer` + `reviewer_override` append) ✓
- M9-F01 Executive summary + verdict: Task 5 (summary agent) + Task 4 pipeline writes verdict ✓
- M9-F02 Report sections: Task 6 (`ReportResponse` exposes all sections) ✓
- <5 min turnaround: BackgroundTasks fires immediately after commit; ~10 LLM calls + 1 summary = ~2-3 min ✓
- Raw scores never to candidate: `GET /reports` uses `require_user` (recruiter only) ✓
- Score scale 1-5: tool schema enforces `minimum: 1, maximum: 5` ✓

**Type consistency:**
- `roll_up` consumes `list[dict]` with `evaluation.competency_scores[].competency` — matches what `score_answer` returns ✓
- `calibrate_answer` accepts `reviewer_id: str` — `claims.sub` is `str` ✓
- `HiringReport.reviewer_override` initialized as list (`[]`) before append ✓
- `evaluation_pipeline` passes `db_factory: Callable[[], Session]` — `SessionLocal` satisfies this ✓

**Placeholder scan:** No TBDs, no "implement later" — all steps contain full code ✓

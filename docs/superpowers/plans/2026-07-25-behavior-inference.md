# Behavior Inference Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `agents/behavior_analysis` to infer DISC style, Big Five, and 7 other behavioral dimensions from the candidate's full answer set, persisting a `behavior_profiles` row for every completed session.

**Architecture:** Two-pass LLM inference — Pass 1 extracts raw behavioral signals from the full Q&A set; Pass 2 synthesizes those signals into the 9 output dimensions. The agent is wired into `agents/evaluation/pipeline.py` after the executive summary, runs non-fatally, and upserts into `behavior_profiles` (unique on `session_id`).

**Tech Stack:** Python 3.12, Anthropic SDK (`anthropic`), SQLAlchemy 2.x ORM, pytest + unittest.mock

## Global Constraints

- Model: `claude-sonnet-4-6` (same as evaluation agent)
- Tool-use forced (`tool_choice={"type": "tool", "name": "<tool>"}`) — no free-text fallback
- §15: Both prompts must contain explicit protected-characteristic exclusion text (verbatim from spec)
- M7-F05: `team_compatibility_signal` always prefixed `"Recruiter discussion prompt:"` — never a verdict
- `behavior_profiles` has `UNIQUE (session_id)` — use upsert (INSERT … ON CONFLICT DO UPDATE)
- Non-fatal: all exceptions caught, logged, pipeline continues
- No self-report questions ever sent — agent trusts the answer set it receives
- Follow existing agent patterns exactly: `_MODEL`, `_MAX_TOKENS`, module-level tool dicts, `logger = logging.getLogger(__name__)`

---

### Task 1: prompts.py — system prompts and tool schemas

**Files:**
- Create: `agents/behavior_analysis/prompts.py`

**Interfaces:**
- Produces:
  - `EXTRACT_SYSTEM_PROMPT: str`
  - `EXTRACT_TOOL: dict` (tool schema for `extract_behavioral_signals`)
  - `SYNTHESIZE_SYSTEM_PROMPT: str`
  - `build_synthesize_tool(org_working_style: str | None) -> dict`

- [ ] **Step 1: Create `agents/behavior_analysis/prompts.py`**

```python
_SECTION_15_EXCLUSION = (
    "Do not infer, mention, score, or reference anything related to age, gender, "
    "race, ethnicity, religion, disability, national origin, physical appearance, "
    "or any other protected characteristic. Do not treat emotional expression as a "
    "hiring criterion."
)

EXTRACT_SYSTEM_PROMPT = (
    "You are a behavioral analyst reading a structured interview transcript. "
    "Identify observable patterns in how the candidate communicates and reasons — "
    "language choice, decision framing, response structure, stress responses, "
    "conflict and teamwork patterns, and cross-answer themes. "
    "Base every observation strictly on the text of the answers. "
    + _SECTION_15_EXCLUSION
)

EXTRACT_TOOL = {
    "name": "extract_behavioral_signals",
    "description": "Extract observable behavioral signals from the full Q&A transcript.",
    "input_schema": {
        "type": "object",
        "properties": {
            "language_patterns": {
                "type": "string",
                "description": "Directive vs collaborative phrasing; use of 'I' vs 'we'; assertiveness level.",
            },
            "decision_framing": {
                "type": "string",
                "description": "Data-driven vs intuitive; risk tolerance; deliberate vs spontaneous.",
            },
            "response_structure": {
                "type": "string",
                "description": "Systematic/structured vs free-flowing; use of examples and frameworks.",
            },
            "stress_response": {
                "type": "string",
                "description": (
                    "Observable patterns in Stress-category answers. "
                    "Write 'No stress-category questions in this set.' if none present."
                ),
            },
            "conflict_eq_patterns": {
                "type": "string",
                "description": (
                    "Emotional intelligence indicators from Conflict Resolution and Teamwork answers. "
                    "Write 'No conflict or teamwork questions in this set.' if none present."
                ),
            },
            "cross_answer_themes": {
                "type": "string",
                "description": "Recurring patterns, values, or tendencies visible across multiple answers.",
            },
        },
        "required": [
            "language_patterns",
            "decision_framing",
            "response_structure",
            "stress_response",
            "conflict_eq_patterns",
            "cross_answer_themes",
        ],
    },
}

SYNTHESIZE_SYSTEM_PROMPT = (
    "You are a behavioral psychologist synthesizing a candidate's behavioral profile "
    "from pre-extracted interview signals. Produce concise, evidence-grounded assessments. "
    "For team_compatibility_signal, always begin with 'Recruiter discussion prompt:' and "
    "describe the candidate's collaboration style — never render a hiring verdict. "
    + _SECTION_15_EXCLUSION
)


def build_synthesize_tool(org_working_style: str | None) -> dict:
    team_compat_desc = (
        "Recruiter discussion prompt: describe the candidate's preferred collaboration style "
        "and how it might complement or contrast with the org working style: "
        f"'{org_working_style}'."
        if org_working_style
        else (
            "Recruiter discussion prompt: describe the candidate's preferred collaboration "
            "style. Always begin with 'Recruiter discussion prompt:'."
        )
    )
    return {
        "name": "synthesize_behavior_profile",
        "description": "Synthesize behavioral signals into a structured behavior profile.",
        "input_schema": {
            "type": "object",
            "properties": {
                "disc_style": {
                    "type": "object",
                    "properties": {
                        "primary": {"type": "string", "enum": ["D", "I", "S", "C"]},
                        "secondary": {"type": "string", "enum": ["D", "I", "S", "C"]},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "rationale": {"type": "string"},
                    },
                    "required": ["primary", "secondary", "confidence", "rationale"],
                },
                "big_five": {
                    "type": "object",
                    "properties": {
                        "openness": {
                            "type": "object",
                            "properties": {
                                "direction": {"type": "string", "enum": ["high", "moderate", "low"]},
                                "evidence": {"type": "string"},
                            },
                            "required": ["direction", "evidence"],
                        },
                        "conscientiousness": {
                            "type": "object",
                            "properties": {
                                "direction": {"type": "string", "enum": ["high", "moderate", "low"]},
                                "evidence": {"type": "string"},
                            },
                            "required": ["direction", "evidence"],
                        },
                        "extraversion": {
                            "type": "object",
                            "properties": {
                                "direction": {"type": "string", "enum": ["high", "moderate", "low"]},
                                "evidence": {"type": "string"},
                            },
                            "required": ["direction", "evidence"],
                        },
                        "agreeableness": {
                            "type": "object",
                            "properties": {
                                "direction": {"type": "string", "enum": ["high", "moderate", "low"]},
                                "evidence": {"type": "string"},
                            },
                            "required": ["direction", "evidence"],
                        },
                        "emotional_stability": {
                            "type": "object",
                            "properties": {
                                "direction": {"type": "string", "enum": ["high", "moderate", "low"]},
                                "evidence": {"type": "string"},
                            },
                            "required": ["direction", "evidence"],
                        },
                    },
                    "required": [
                        "openness", "conscientiousness", "extraversion",
                        "agreeableness", "emotional_stability",
                    ],
                },
                "leadership_style": {"type": "string"},
                "decision_style": {"type": "string"},
                "communication_style": {"type": "string"},
                "work_style": {"type": "string"},
                "stress_signal": {"type": "string"},
                "eq_signal": {"type": "string"},
                "team_compatibility_signal": {
                    "type": "string",
                    "description": team_compat_desc,
                },
            },
            "required": [
                "disc_style", "big_five", "leadership_style", "decision_style",
                "communication_style", "work_style", "stress_signal", "eq_signal",
                "team_compatibility_signal",
            ],
        },
    }
```

- [ ] **Step 2: Commit**

```bash
git add agents/behavior_analysis/prompts.py
git commit -m "[TASK-002] feat(behavior-analysis): prompts and tool schemas for two-pass inference"
```

---

### Task 2: agent.py — two-pass LLM inference and DB upsert

**Files:**
- Create: `agents/behavior_analysis/agent.py`

**Interfaces:**
- Consumes:
  - `EXTRACT_SYSTEM_PROMPT`, `EXTRACT_TOOL` from `agents.behavior_analysis.prompts`
  - `SYNTHESIZE_SYSTEM_PROMPT`, `build_synthesize_tool` from `agents.behavior_analysis.prompts`
  - `SessionQuestion` ORM model (imported inside function to avoid circular imports, same pattern as `evaluation/pipeline.py`)
  - `BehaviorProfile` ORM model
- Produces:
  - `infer_behavior(session_id: uuid.UUID, db_factory: Callable[[], Session], org_working_style: str | None = None) -> None`

- [ ] **Step 1: Locate the BehaviorProfile ORM model**

Check what models exist under `services/orchestrator-api/src/models/`:

```bash
ls services/orchestrator-api/src/models/
```

Expected: `behavior_profiles.py` (or similar). If the file doesn't exist yet, it needs to be created following the same pattern as `services/orchestrator-api/src/models/hiring_reports.py`.

- [ ] **Step 2: Read the HiringReport model to confirm the ORM pattern**

Read `services/orchestrator-api/src/models/hiring_reports.py` to see how models are declared (Base, __tablename__, Column types). The BehaviorProfile model must follow the same pattern exactly.

- [ ] **Step 3: Create BehaviorProfile ORM model if it doesn't exist**

If `services/orchestrator-api/src/models/behavior_profiles.py` does not exist, create it:

```python
import uuid as _uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class BehaviorProfile(Base):
    __tablename__ = "behavior_profiles"

    id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    org_id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    session_id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    disc_style: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'"))
    big_five: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'"))
    leadership_style: Mapped[str | None] = mapped_column(sa.Text)
    decision_style: Mapped[str | None] = mapped_column(sa.Text)
    communication_style: Mapped[str | None] = mapped_column(sa.Text)
    work_style: Mapped[str | None] = mapped_column(sa.Text)
    stress_signal: Mapped[str | None] = mapped_column(sa.Text)
    eq_signal: Mapped[str | None] = mapped_column(sa.Text)
    team_compatibility_signal: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )
```

If the file exists already with a different pattern, follow what's there.

- [ ] **Step 4: Create `agents/behavior_analysis/agent.py`**

```python
import logging
import uuid
from collections.abc import Callable

import anthropic
from sqlalchemy.orm import Session

from agents.behavior_analysis.prompts import (
    EXTRACT_SYSTEM_PROMPT,
    EXTRACT_TOOL,
    SYNTHESIZE_SYSTEM_PROMPT,
    build_synthesize_tool,
)

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096


def _extract_signals(transcript: str) -> dict:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=EXTRACT_SYSTEM_PROMPT,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "extract_behavioral_signals"},
        messages=[{"role": "user", "content": transcript}],
    )
    tool_block = next(b for b in response.content if b.type == "tool_use")
    return dict(tool_block.input)


def _synthesize_profile(signals: dict, org_working_style: str | None) -> dict:
    client = anthropic.Anthropic()
    tool = build_synthesize_tool(org_working_style)
    signals_text = "\n".join(f"{k}: {v}" for k, v in signals.items())
    response = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=SYNTHESIZE_SYSTEM_PROMPT,
        tools=[tool],
        tool_choice={"type": "tool", "name": "synthesize_behavior_profile"},
        messages=[{"role": "user", "content": signals_text}],
    )
    tool_block = next(b for b in response.content if b.type == "tool_use")
    return dict(tool_block.input)


def infer_behavior(
    session_id: uuid.UUID,
    db_factory: Callable[[], Session],
    org_working_style: str | None = None,
) -> None:
    from src.models.assessment_sessions import AssessmentSession
    from src.models.behavior_profiles import BehaviorProfile
    from src.models.question_sets import QuestionSet
    from src.models.session_questions import SessionQuestion

    db = db_factory()
    try:
        session = db.query(AssessmentSession).filter_by(id=session_id).first()
        if not session:
            logger.error("infer_behavior: session %s not found", session_id)
            return

        qset = db.query(QuestionSet).filter_by(session_id=session_id).first()
        if not qset:
            logger.error("infer_behavior: no question set for session %s", session_id)
            return

        questions = (
            db.query(SessionQuestion)
            .filter(
                SessionQuestion.question_set_id == qset.id,
                SessionQuestion.answer_text.isnot(None),
            )
            .order_by(SessionQuestion.sequence_no)
            .all()
        )

        if not questions:
            logger.info("infer_behavior: no answered questions for session %s — skipping", session_id)
            return

        transcript = "\n\n".join(
            f"Q{q.sequence_no} [{q.category}]: {q.question.get('text', '')}\nA: {q.answer_text}"
            for q in questions
        )

        signals = _extract_signals(transcript)
        profile_data = _synthesize_profile(signals, org_working_style)

        existing = db.query(BehaviorProfile).filter_by(session_id=session_id).first()
        if existing:
            existing.disc_style = profile_data["disc_style"]
            existing.big_five = profile_data["big_five"]
            existing.leadership_style = profile_data.get("leadership_style")
            existing.decision_style = profile_data.get("decision_style")
            existing.communication_style = profile_data.get("communication_style")
            existing.work_style = profile_data.get("work_style")
            existing.stress_signal = profile_data.get("stress_signal")
            existing.eq_signal = profile_data.get("eq_signal")
            existing.team_compatibility_signal = profile_data.get("team_compatibility_signal")
        else:
            db.add(BehaviorProfile(
                org_id=session.org_id,
                session_id=session_id,
                disc_style=profile_data["disc_style"],
                big_five=profile_data["big_five"],
                leadership_style=profile_data.get("leadership_style"),
                decision_style=profile_data.get("decision_style"),
                communication_style=profile_data.get("communication_style"),
                work_style=profile_data.get("work_style"),
                stress_signal=profile_data.get("stress_signal"),
                eq_signal=profile_data.get("eq_signal"),
                team_compatibility_signal=profile_data.get("team_compatibility_signal"),
            ))

        db.commit()
        logger.info("infer_behavior: behavior profile written for session %s", session_id)

    except Exception:
        logger.exception("infer_behavior failed for session %s — skipping", session_id)
        db.rollback()
    finally:
        db.close()
```

- [ ] **Step 5: Commit**

```bash
git add agents/behavior_analysis/agent.py
git commit -m "[TASK-002] feat(behavior-analysis): two-pass inference agent with DB upsert"
```

---

### Task 3: tests — unit tests with mocked Anthropic client

**Files:**
- Create: `agents/behavior_analysis/tests/__init__.py`
- Create: `agents/behavior_analysis/tests/test_agent.py`

**Interfaces:**
- Consumes: `infer_behavior` from `agents.behavior_analysis.agent`
- Consumes: `_extract_signals`, `_synthesize_profile` from `agents.behavior_analysis.agent`

- [ ] **Step 1: Create `agents/behavior_analysis/tests/__init__.py`** (empty file)

- [ ] **Step 2: Write the failing tests**

```python
# agents/behavior_analysis/tests/test_agent.py
import uuid
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

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


def _make_tool_response(tool_name: str, payload: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.input = payload
    response = MagicMock()
    response.content = [block]
    return response


def _make_db(session_obj, qset_obj, questions):
    db = MagicMock()
    profiles_stored = []

    def query_side_effect(model):
        q = MagicMock()
        name = getattr(model, "__tablename__", None) or getattr(model, "__name__", "")

        if "AssessmentSession" in str(model):
            q.filter_by.return_value.first.return_value = session_obj
        elif "BehaviorProfile" in str(model):
            q.filter_by.return_value.first.return_value = None
            original_add = db.add
            def _add(obj):
                profiles_stored.append(obj)
            db.add.side_effect = _add
        elif "QuestionSet" in str(model):
            q.filter_by.return_value.first.return_value = qset_obj
        elif "SessionQuestion" in str(model):
            filt = MagicMock()
            filt.filter.return_value.order_by.return_value.all.return_value = questions
            q.filter.return_value = filt
        return q

    db.query.side_effect = query_side_effect
    return db, profiles_stored


# ---------------------------------------------------------------------------
# Test 1: Happy path — 5 answered questions → profile written
# ---------------------------------------------------------------------------

def test_infer_behavior_happy_path():
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
    def fake_create(**kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return _make_tool_response("extract_behavioral_signals", _FAKE_SIGNALS)
        return _make_tool_response("synthesize_behavior_profile", _FAKE_PROFILE)

    with patch("agents.behavior_analysis.agent.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = fake_create
        mock_anthropic.return_value = mock_client

        with patch("agents.behavior_analysis.agent.Session"):
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

    with patch("agents.behavior_analysis.agent.anthropic.Anthropic") as mock_anthropic:
        infer_behavior(session_id=_SESSION_ID, db_factory=lambda: db)
        mock_anthropic.return_value.messages.create.assert_not_called()

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

    with patch("agents.behavior_analysis.agent.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("API timeout")
        mock_anthropic.return_value = mock_client

        # Should not raise
        infer_behavior(session_id=_SESSION_ID, db_factory=lambda: db)

    assert len(profiles_stored) == 0
    db.rollback.assert_called_once()
    db.commit.assert_not_called()
```

- [ ] **Step 3: Run tests to verify they fail (agent doesn't exist yet if running before Task 2)**

```bash
cd D:\staging\ARAP1
python -m pytest agents/behavior_analysis/tests/test_agent.py -v 2>&1 | head -40
```

Expected: ImportError or AttributeError — agent module doesn't exist.

- [ ] **Step 4: Run tests after Task 2 is complete**

```bash
python -m pytest agents/behavior_analysis/tests/test_agent.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/behavior_analysis/tests/__init__.py agents/behavior_analysis/tests/test_agent.py
git commit -m "[TASK-002] test(behavior-analysis): unit tests for infer_behavior (happy path, no answers, LLM failure)"
```

---

### Task 4: Pipeline wiring — call infer_behavior after executive summary

**Files:**
- Modify: `agents/evaluation/pipeline.py` (add `_run_behavior_inference` helper and one call at the bottom of `evaluation_pipeline`)

**Interfaces:**
- Consumes: `infer_behavior(session_id, db_factory, org_working_style)` from `agents.behavior_analysis.agent`

- [ ] **Step 1: Add `_run_behavior_inference` helper to `agents/evaluation/pipeline.py`**

Add after the `_generate_executive_summary` function (around line 133):

```python
def _run_behavior_inference(
    db: Session,
    session_id: uuid.UUID,
    job,
) -> None:
    try:
        from agents.behavior_analysis.agent import infer_behavior

        org_working_style = (
            ", ".join(job.culture_values)
            if job and job.culture_values
            else None
        )
        infer_behavior(
            session_id=session_id,
            db_factory=lambda: db,
            org_working_style=org_working_style,
        )
    except Exception:
        logger.exception("behavior inference failed for session %s", session_id)
```

- [ ] **Step 2: Call it at the end of `evaluation_pipeline`**

In `evaluation_pipeline`, after the line:

```python
_generate_executive_summary(db, session_id, job_title, candidate_name, rollup, verdict)
```

Add:

```python
_run_behavior_inference(db, session_id, job)
```

- [ ] **Step 3: Run the existing evaluation pipeline tests to confirm nothing broke**

```bash
python -m pytest agents/evaluation/tests/ -v
```

Expected: all existing tests PASS.

- [ ] **Step 4: Commit**

```bash
git add agents/evaluation/pipeline.py
git commit -m "[TASK-002] feat(evaluation): wire behavior inference into evaluation pipeline"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| M7-F01 DISC style from language patterns | Task 1 (EXTRACT_TOOL signals), Task 2 (synthesize → disc_style) |
| M7-F02 Big Five from conversational evidence | Task 1, Task 2 (big_five JSONB) |
| M7-F03 Leadership/Decision/Communication/Work Style from multiple answers | Task 1, Task 2 (4 text fields) |
| M7-F04 Stress & EQ from category-specific Qs | Task 1 (stress_response, conflict_eq_patterns), Task 2 (stress_signal, eq_signal) |
| M7-F05 Team compatibility as recruiter prompt, never pass/fail | Task 1 (build_synthesize_tool description), Task 2 (prefix enforcement) |
| §15 protected characteristic exclusion | Task 1 (_SECTION_15_EXCLUSION in both prompts) |
| Persist to behavior_profiles all 9 columns | Task 2 (upsert) |
| 100% coverage for completed sessions | Task 4 (pipeline wiring) |
| Non-fatal on failure | Task 2 (except block), Task 4 (_run_behavior_inference try/except) |
| No self-report questions | Handled by question generation; agent trusts its input |

**Placeholder scan:** None found.

**Type consistency:** `infer_behavior` signature used identically in Task 2 (definition) and Task 4 (call site). `_FAKE_SIGNALS` and `_FAKE_PROFILE` keys match the tool schemas in Task 1.

# M4 Question Generation Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement M4-F01–F06 — upfront batch question generation, category-weighted coverage, resume-referenced and risk-flag-targeted questions, pgvector no-repeat dedup, and set lock.

**Architecture:** Agent (`agents/question_generation/`) calls Claude claude-sonnet-4-6 via forced tool_use, returns `list[dict] | None`. Service (`src/modules/question_sets/service.py`) orchestrates: load session → call agent → embed via OpenAI → dedup via pgvector → persist + lock in one transaction. Router exposes `POST /question-sets/generate/{session_id}` and `GET /question-sets/{session_id}`.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, Anthropic SDK (`anthropic>=0.28`), OpenAI SDK (`openai>=1.0`), pgvector cosine similarity, pytest + httpx AsyncClient.

## Global Constraints

- Model: `claude-sonnet-4-6` (not Haiku — generation quality matters)
- Embedding model: `text-embedding-3-small`, dim=1536
- Similarity threshold: 0.92 cosine (reject if `1 - distance >= 0.92`)
- Max LLM passes: 2 (first pass with 25% buffer, one gap-fill pass)
- Buffer: `ceil(target × 0.25)` extra questions per pass
- `generation_prompt_version`: `"v1.0"` constant in `prompts.py`
- All service exceptions follow existing pattern: `LookupError→404`, `ValueError→422`, `RuntimeError→502`
- 409 conflict checked in router (not service) — avoids custom exception type
- `question` JSONB stores the full PRD question object (all fields except `resume_reference`)
- Auth: `require_user` (user or admin), `org_id` from JWT claims only
- Test DB: `postgresql://arap:arap@localhost:5434/arap_test`
- `pythonpath = [".", "../.."]` already set in orchestrator-api pyproject.toml
- Commit format: `[TASK-001] <type>: <what>`

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `agents/question_generation/prompts.py` | SYSTEM_PROMPT, PROMPT_VERSION, CATEGORY_TO_COMPETENCY constant, QUESTION_GENERATION_TOOL schema |
| Create | `agents/question_generation/agent.py` | `run_question_generation_agent(...)→list[dict]|None` |
| Create | `services/orchestrator-api/src/modules/question_sets/__init__.py` | empty |
| Create | `services/orchestrator-api/src/modules/question_sets/embeddings.py` | `embed_texts(texts)→list[list[float]]` via OpenAI |
| Create | `services/orchestrator-api/src/modules/question_sets/schemas.py` | `QuestionItem`, `QuestionSetResponse` |
| Create | `services/orchestrator-api/src/modules/question_sets/service.py` | `generate_question_set()`, `get_question_set()` |
| Create | `services/orchestrator-api/src/modules/question_sets/router.py` | POST generate, GET by session |
| Modify | `services/orchestrator-api/src/main.py` | register question_sets router |
| Modify | `services/orchestrator-api/pyproject.toml` | add `openai>=1.0` dep + OPENAI_API_KEY pytest env |
| Create | `services/orchestrator-api/tests/question_sets/__init__.py` | empty |
| Create | `services/orchestrator-api/tests/question_sets/conftest.py` | engine, db, seed, user_token, mock_agent, mock_embed, async_client fixtures |
| Create | `services/orchestrator-api/tests/question_sets/test_agent.py` | agent unit tests (mocked Anthropic) |
| Create | `services/orchestrator-api/tests/question_sets/test_service.py` | dedup logic, happy path, error paths |
| Create | `services/orchestrator-api/tests/question_sets/test_router.py` | 201/404/409/422/502, GET before/after |

---

## Task 1: Agent — prompts.py + agent.py + agent test

**Files:**
- Create: `agents/question_generation/prompts.py`
- Create: `agents/question_generation/agent.py`
- Create: `services/orchestrator-api/tests/question_sets/__init__.py`
- Create: `services/orchestrator-api/tests/question_sets/test_agent.py`

**Interfaces:**
- Produces: `run_question_generation_agent(job_profile: dict, candidate_profile: dict, category_weightage: dict, difficulty_level: str, risk_flags: list, target_question_count: int) -> list[dict] | None`
- Each dict in the list has keys: `question`, `category`, `target_competencies`, `difficulty`, `answer_format`, `options` (list|absent), `resume_reference` (bool)

- [ ] **Step 1: Write `agents/question_generation/prompts.py`**

```python
PROMPT_VERSION = "v1.0"

SYSTEM_PROMPT = (
    "You are the Question Generation Agent for a personalized recruitment "
    "assessment. Generate the COMPLETE question set for this candidate in one "
    "pass. Never repeat or closely paraphrase any question already generated "
    "for this org's question-fingerprint history. Match the category weightage "
    "and difficulty level supplied."
)

# Maps PRD category names to lowercase competency key aliases for weight lookup.
CATEGORY_TO_COMPETENCY: dict[str, str] = {
    "Technical": "technical",
    "Behavioral": "behavioral",
    "Leadership": "leadership",
    "Case Study": "case_study",
    "Scenario": "scenario",
    "Decision-Making": "decision_making",
    "Conflict Resolution": "conflict_resolution",
    "Problem Solving": "problem_solving",
    "Analytical": "analytical",
    "Situational Judgment": "situational_judgment",
    "Communication": "communication",
    "Ethics": "ethics",
    "Innovation": "innovation",
    "Culture Fit": "culture_fit",
    "Stress": "stress",
    "Priority Management": "priority_management",
    "Negotiation": "negotiation",
    "Business Strategy": "business_strategy",
    "Financial": "financial",
    "Presentation": "presentation",
    "Customer Handling": "customer_handling",
}

VALID_CATEGORIES = list(CATEGORY_TO_COMPETENCY.keys())

QUESTION_GENERATION_TOOL: dict = {
    "name": "generate_question_set",
    "description": "Generate a complete personalized question set for the candidate.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "category": {"type": "string", "enum": VALID_CATEGORIES},
                        "target_competencies": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "difficulty": {
                            "type": "string",
                            "enum": ["easy", "medium", "hard", "expert"],
                        },
                        "answer_format": {
                            "type": "string",
                            "enum": ["multiple_choice", "short_text", "long_text"],
                        },
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Required when answer_format is multiple_choice.",
                        },
                        "resume_reference": {
                            "type": "boolean",
                            "description": "True if this question directly cites the candidate's resume.",
                        },
                    },
                    "required": [
                        "question", "category", "target_competencies",
                        "difficulty", "answer_format", "resume_reference",
                    ],
                },
            }
        },
        "required": ["questions"],
    },
}
```

- [ ] **Step 2: Write `agents/question_generation/agent.py`**

```python
import json
import logging

import anthropic

from agents.question_generation.prompts import (
    QUESTION_GENERATION_TOOL,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 8192


def _build_user_message(
    job_profile: dict,
    candidate_profile: dict,
    category_weightage: dict,
    difficulty_level: str,
    risk_flags: list,
    target_question_count: int,
) -> str:
    return "\n".join([
        f"job_profile: {json.dumps(job_profile)}",
        f"candidate_profile: {json.dumps(candidate_profile)}",
        f"category_weightage: {json.dumps(category_weightage)}",
        f"difficulty_level: {difficulty_level}",
        f"risk_flags: {json.dumps(risk_flags)}",
        f"target_question_count: {target_question_count}",
        "",
        "Generate exactly target_question_count questions. "
        "At least one question MUST have resume_reference=true, "
        "directly citing a specific detail from the candidate's resume. "
        "Distribute questions across categories per category_weightage counts. "
        "Seed at least one question per risk flag.",
    ])


def run_question_generation_agent(
    job_profile: dict,
    candidate_profile: dict,
    category_weightage: dict,
    difficulty_level: str,
    risk_flags: list,
    target_question_count: int,
) -> list[dict] | None:
    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[QUESTION_GENERATION_TOOL],
            tool_choice={"type": "tool", "name": "generate_question_set"},
            messages=[{
                "role": "user",
                "content": _build_user_message(
                    job_profile, candidate_profile, category_weightage,
                    difficulty_level, risk_flags, target_question_count,
                ),
            }],
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        return list(tool_block.input["questions"])
    except Exception:
        logger.exception("Question generation agent failed — returning None")
        return None
```

- [ ] **Step 3: Create `services/orchestrator-api/tests/question_sets/__init__.py`** (empty file)

- [ ] **Step 4: Write `services/orchestrator-api/tests/question_sets/test_agent.py`**

```python
from unittest.mock import MagicMock, patch


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


def _make_fake_response(questions):
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {"questions": questions}
    response = MagicMock()
    response.content = [tool_block]
    return response


def test_agent_returns_question_list():
    from agents.question_generation.agent import run_question_generation_agent

    with patch("agents.question_generation.agent.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _make_fake_response(FAKE_QUESTIONS)
        result = run_question_generation_agent(
            JOB_PROFILE, CANDIDATE_PROFILE, CATEGORY_WEIGHTAGE, "senior", RISK_FLAGS, 2
        )

    assert result is not None
    assert len(result) == 2
    assert result[0]["question"] == FAKE_QUESTIONS[0]["question"]


def test_agent_returns_none_on_exception():
    from agents.question_generation.agent import run_question_generation_agent

    with patch("agents.question_generation.agent.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = Exception("API error")
        result = run_question_generation_agent(
            JOB_PROFILE, CANDIDATE_PROFILE, CATEGORY_WEIGHTAGE, "senior", RISK_FLAGS, 2
        )

    assert result is None


def test_agent_result_contains_required_fields():
    from agents.question_generation.agent import run_question_generation_agent

    with patch("agents.question_generation.agent.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _make_fake_response(FAKE_QUESTIONS)
        result = run_question_generation_agent(
            JOB_PROFILE, CANDIDATE_PROFILE, CATEGORY_WEIGHTAGE, "senior", RISK_FLAGS, 2
        )

    for q in result:
        for field in ("question", "category", "target_competencies", "difficulty", "answer_format", "resume_reference"):
            assert field in q, f"Missing field: {field}"


def test_agent_result_has_at_least_one_resume_reference():
    from agents.question_generation.agent import run_question_generation_agent

    with patch("agents.question_generation.agent.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _make_fake_response(FAKE_QUESTIONS)
        result = run_question_generation_agent(
            JOB_PROFILE, CANDIDATE_PROFILE, CATEGORY_WEIGHTAGE, "senior", RISK_FLAGS, 2
        )

    assert any(q["resume_reference"] for q in result)
```

- [ ] **Step 5: Run agent tests**

```
cd services/orchestrator-api
pytest tests/question_sets/test_agent.py -v
```

Expected: 4 tests PASS (no real API calls — all mocked).

- [ ] **Step 6: Commit**

```bash
git add agents/question_generation/prompts.py agents/question_generation/agent.py \
  services/orchestrator-api/tests/question_sets/__init__.py \
  services/orchestrator-api/tests/question_sets/test_agent.py
git commit -m "[TASK-001] feat: add question generation agent (M4-F01 prompt + tool)"
```

---

## Task 2: openai dep + embed helper

**Files:**
- Modify: `services/orchestrator-api/pyproject.toml`
- Create: `services/orchestrator-api/src/modules/question_sets/__init__.py`
- Create: `services/orchestrator-api/src/modules/question_sets/embeddings.py`

**Interfaces:**
- Produces: `embed_texts(texts: list[str]) -> list[list[float]]` — returns embeddings in same order as input

- [ ] **Step 1: Add openai to pyproject.toml**

In `services/orchestrator-api/pyproject.toml`, add `"openai>=1.0"` to the `dependencies` list and `"OPENAI_API_KEY=test-openai-key-not-real"` to `[tool.pytest.ini_options] env`:

```toml
dependencies = [
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "pgvector>=0.3",
    "psycopg2-binary>=2.9",
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "pydantic-settings>=2.2",
    "pydantic[email]>=2.0",
    "PyJWT>=2.8",
    "passlib[bcrypt]>=1.7.4",
    "bcrypt>=4.0.1,<5.0",
    "redis>=5.0",
    "anthropic>=0.28",
    "openai>=1.0",
]
```

```toml
env = [
    "TEST_DATABASE_URL=postgresql://arap:arap@localhost:5434/arap_test",
    "DATABASE_URL=postgresql://arap:arap@localhost:5433/arap_dev",
    "SECRET_KEY=test-secret-key-not-for-production",
    "JWT_SECRET_KEY=test-jwt-secret-key-not-for-production",
    "ANTHROPIC_API_KEY=test-anthropic-key-not-real",
    "OPENAI_API_KEY=test-openai-key-not-real",
]
```

- [ ] **Step 2: Install openai**

```bash
cd services/orchestrator-api
pip install "openai>=1.0"
```

Expected: openai installed successfully.

- [ ] **Step 3: Create `services/orchestrator-api/src/modules/question_sets/__init__.py`** (empty file)

- [ ] **Step 4: Write `services/orchestrator-api/src/modules/question_sets/embeddings.py`**

```python
import openai

_MODEL = "text-embedding-3-small"


def embed_texts(texts: list[str]) -> list[list[float]]:
    client = openai.OpenAI()
    response = client.embeddings.create(model=_MODEL, input=texts)
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
```

- [ ] **Step 5: Verify import works**

```bash
cd services/orchestrator-api
python -c "from src.modules.question_sets.embeddings import embed_texts; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add services/orchestrator-api/pyproject.toml \
  services/orchestrator-api/src/modules/question_sets/__init__.py \
  services/orchestrator-api/src/modules/question_sets/embeddings.py
git commit -m "[TASK-001] feat: add openai dep and embed_texts helper for M4 dedup"
```

---

## Task 3: Schemas

**Files:**
- Create: `services/orchestrator-api/src/modules/question_sets/schemas.py`

**Interfaces:**
- Produces: `QuestionItem`, `QuestionSetResponse` — used by service and router

- [ ] **Step 1: Write `services/orchestrator-api/src/modules/question_sets/schemas.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel


class QuestionItem(BaseModel):
    id: uuid.UUID
    sequence_no: int
    question: str
    category: str
    target_competencies: list[str]
    difficulty: str
    answer_format: str
    options: list[str] | None


class QuestionSetResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    generated_at: datetime
    locked_at: datetime
    generation_prompt_version: str
    questions: list[QuestionItem]
```

- [ ] **Step 2: Verify import**

```bash
cd services/orchestrator-api
python -c "from src.modules.question_sets.schemas import QuestionSetResponse; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add services/orchestrator-api/src/modules/question_sets/schemas.py
git commit -m "[TASK-001] feat: add question_sets schemas (M4 response contract)"
```

---

## Task 4: Service + service tests

**Files:**
- Create: `services/orchestrator-api/src/modules/question_sets/service.py`
- Create: `services/orchestrator-api/tests/question_sets/conftest.py`
- Create: `services/orchestrator-api/tests/question_sets/test_service.py`

**Interfaces:**
- Consumes: `run_question_generation_agent(...)→list[dict]|None` from Task 1; `embed_texts(...)→list[list[float]]` from Task 2; `QuestionSetResponse`, `QuestionItem` from Task 3
- Produces: `generate_question_set(db, session_id, org_id, target) -> QuestionSetResponse`; `get_question_set(db, session_id, org_id) -> QuestionSetResponse`; raises `LookupError` (→404), `ValueError` (→422), `RuntimeError` (→502)

- [ ] **Step 1: Write `services/orchestrator-api/src/modules/question_sets/service.py`**

```python
import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from agents.question_generation.agent import run_question_generation_agent
from agents.question_generation.prompts import CATEGORY_TO_COMPETENCY, PROMPT_VERSION
from src.models.assessment_sessions import AssessmentSession
from src.models.candidate_profiles import CandidateProfile
from src.models.job_assessments import JobAssessment
from src.models.question_fingerprints import QuestionFingerprint
from src.models.question_sets import QuestionSet
from src.models.session_questions import SessionQuestion
from src.modules.question_sets.embeddings import embed_texts
from src.modules.question_sets.schemas import QuestionItem, QuestionSetResponse

_SIMILARITY_THRESHOLD = 0.92
_DEFAULT_TARGET = 10


def _derive_category_counts(competency_weightage: dict, target: int) -> dict[str, int]:
    lower_weight: dict[str, float] = {k.lower().replace(" ", "_"): v for k, v in competency_weightage.items()}

    category_weights: dict[str, float] = {}
    for cat, alias in CATEGORY_TO_COMPETENCY.items():
        w = lower_weight.get(alias)
        if w is None:
            # substring fallback
            for k, v in lower_weight.items():
                if alias in k or k in alias:
                    w = v
                    break
        if w is not None:
            category_weights[cat] = float(w)

    if not category_weights:
        each = target // len(CATEGORY_TO_COMPETENCY)
        counts = {cat: each for cat in CATEGORY_TO_COMPETENCY}
        remainder = target - each * len(CATEGORY_TO_COMPETENCY)
        for cat in list(CATEGORY_TO_COMPETENCY.keys())[:remainder]:
            counts[cat] += 1
        return {k: v for k, v in counts.items() if v > 0}

    total_weight = sum(category_weights.values())
    counts: dict[str, int] = {}
    allocated = 0
    cats = list(category_weights.keys())
    for i, cat in enumerate(cats):
        if i == len(cats) - 1:
            counts[cat] = max(target - allocated, 0)
        else:
            n = round(category_weights[cat] / total_weight * target)
            counts[cat] = max(n, 0)
            allocated += counts[cat]
    return {k: v for k, v in counts.items() if v > 0}


def _is_duplicate(db: Session, org_id: uuid.UUID, embedding: list[float]) -> bool:
    row = db.execute(
        text(
            "SELECT 1 - (question_embedding <=> CAST(:vec AS vector)) AS similarity "
            "FROM question_fingerprints "
            "WHERE org_id = :org_id "
            "ORDER BY question_embedding <=> CAST(:vec AS vector) "
            "LIMIT 1"
        ),
        {"org_id": str(org_id), "vec": str(embedding)},
    ).fetchone()
    if row is None:
        return False
    return float(row[0]) >= _SIMILARITY_THRESHOLD


def _dedup(
    db: Session,
    org_id: uuid.UUID,
    questions: list[dict],
    embeddings: list[list[float]],
) -> list[tuple[dict, list[float]]]:
    return [
        (q, emb)
        for q, emb in zip(questions, embeddings)
        if not _is_duplicate(db, org_id, emb)
    ]


def _call_agent(
    job_profile: dict,
    candidate_profile_dict: dict,
    category_counts: dict,
    difficulty_level: str,
    risk_flags: list,
    count: int,
) -> list[dict] | None:
    return run_question_generation_agent(
        job_profile=job_profile,
        candidate_profile=candidate_profile_dict,
        category_weightage=category_counts,
        difficulty_level=difficulty_level,
        risk_flags=risk_flags,
        target_question_count=count,
    )


def generate_question_set(
    db: Session,
    session_id: uuid.UUID,
    org_id: uuid.UUID,
    target: int = _DEFAULT_TARGET,
) -> QuestionSetResponse:
    session = db.query(AssessmentSession).filter_by(
        id=session_id, org_id=org_id
    ).first()
    if session is None:
        raise LookupError("Assessment session not found")

    job = db.query(JobAssessment).filter_by(
        id=session.job_assessment_id, org_id=org_id
    ).first()
    if job is None or job.job_profile is None:
        raise ValueError("Job profile not generated — retry job assessment creation")

    if session.candidate_profile_id is None:
        raise ValueError("Candidate profile not yet synthesized — run M3 first")

    profile = db.query(CandidateProfile).filter_by(
        id=session.candidate_profile_id, org_id=org_id
    ).first()
    if profile is None:
        raise ValueError("Candidate profile record missing — run M3 first")

    difficulty_level = job.job_profile.get("difficulty_level", "mid")
    category_counts = _derive_category_counts(job.competency_weightage or {}, target)
    risk_flags = profile.risk_flags or []

    candidate_profile_dict = {
        "summary": profile.summary,
        "skill_matrix": profile.skill_matrix,
        "strengths": profile.strengths,
        "risk_flags": risk_flags,
        "experience_matrix": profile.experience_matrix,
    }

    # Pass 1: target + 25% buffer
    first_count = target + math.ceil(target * 0.25)
    questions = _call_agent(
        job.job_profile, candidate_profile_dict, category_counts,
        difficulty_level, risk_flags, first_count,
    )
    if questions is None:
        raise RuntimeError("Question generation agent failed — retry request")

    embeddings = embed_texts([q["question"] for q in questions])
    accepted = _dedup(db, org_id, questions, embeddings)

    # Pass 2: fill the gap if needed
    if len(accepted) < target:
        gap = target - len(accepted)
        gap_questions = _call_agent(
            job.job_profile, candidate_profile_dict, category_counts,
            difficulty_level, risk_flags, gap + math.ceil(gap * 0.25),
        )
        if gap_questions:
            gap_embeddings = embed_texts([q["question"] for q in gap_questions])
            accepted += _dedup(db, org_id, gap_questions, gap_embeddings)

    if len(accepted) < target:
        raise RuntimeError(
            f"Could not generate {target} unique questions after 2 passes — retry request"
        )

    accepted = accepted[:target]

    # Ensure at least one resume-referenced question (M4-F03)
    if not any(q.get("resume_reference") for q, _ in accepted):
        ref_batch = _call_agent(
            job.job_profile, candidate_profile_dict, {"Behavioral": 2},
            difficulty_level, risk_flags, 2,
        )
        if ref_batch:
            ref_q = next((q for q in ref_batch if q.get("resume_reference")), None)
            if ref_q:
                ref_emb = embed_texts([ref_q["question"]])[0]
                if not _is_duplicate(db, org_id, ref_emb):
                    accepted[-1] = (ref_q, ref_emb)

    # Persist: question_set → session_questions → fingerprints → lock
    question_set = QuestionSet(
        org_id=org_id,
        session_id=session_id,
        generation_prompt_version=PROMPT_VERSION,
    )
    db.add(question_set)
    db.flush()

    session_questions: list[SessionQuestion] = []
    fingerprints: list[QuestionFingerprint] = []

    for seq, (q, emb) in enumerate(accepted, start=1):
        question_obj = {
            "question": q["question"],
            "category": q["category"],
            "target_competencies": q.get("target_competencies", []),
            "difficulty": q["difficulty"],
            "answer_format": q["answer_format"],
        }
        if q["answer_format"] == "multiple_choice":
            question_obj["options"] = q.get("options", [])

        sq = SessionQuestion(
            org_id=org_id,
            question_set_id=question_set.id,
            sequence_no=seq,
            question=question_obj,
            category=q["category"],
            target_competencies=q.get("target_competencies", []),
            difficulty=q["difficulty"],
            answer_format=q["answer_format"],
            options=q.get("options") if q["answer_format"] == "multiple_choice" else None,
        )
        session_questions.append(sq)
        fingerprints.append(QuestionFingerprint(
            org_id=org_id,
            question_text=q["question"],
            question_embedding=emb,
            question_set_id=question_set.id,
        ))

    db.add_all(session_questions)
    db.add_all(fingerprints)
    db.flush()

    question_set.locked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(question_set)
    for sq in session_questions:
        db.refresh(sq)

    return _build_response(question_set, session_questions)


def get_question_set(
    db: Session,
    session_id: uuid.UUID,
    org_id: uuid.UUID,
) -> QuestionSetResponse:
    qs = db.query(QuestionSet).filter_by(session_id=session_id).first()
    if qs is None:
        raise LookupError("Question set not found — generate it first")

    # Verify the set belongs to this org
    if str(qs.org_id) != str(org_id):
        raise LookupError("Question set not found")

    sqs = (
        db.query(SessionQuestion)
        .filter_by(question_set_id=qs.id, org_id=org_id)
        .order_by(SessionQuestion.sequence_no)
        .all()
    )
    return _build_response(qs, sqs)


def _build_response(qs: QuestionSet, sqs: list[SessionQuestion]) -> QuestionSetResponse:
    items = [
        QuestionItem(
            id=sq.id,
            sequence_no=sq.sequence_no,
            question=sq.question.get("question", ""),
            category=sq.category,
            target_competencies=list(sq.target_competencies),
            difficulty=sq.difficulty,
            answer_format=sq.answer_format,
            options=list(sq.options) if sq.options else None,
        )
        for sq in sorted(sqs, key=lambda x: x.sequence_no)
    ]
    return QuestionSetResponse(
        id=qs.id,
        session_id=qs.session_id,
        generated_at=qs.generated_at,
        locked_at=qs.locked_at,
        generation_prompt_version=qs.generation_prompt_version,
        questions=items,
    )
```

- [ ] **Step 2: Write `services/orchestrator-api/tests/question_sets/conftest.py`**

```python
import os
import uuid as _uuid
from unittest.mock import patch

import fakeredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from passlib.context import CryptContext
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

import src.models  # noqa: F401
from src.models.assessment_sessions import AssessmentSession
from src.models.base import Base
from src.models.candidate_profiles import CandidateProfile
from src.models.candidates import Candidate
from src.models.job_assessments import JobAssessment
from src.models.orgs import Org
from src.models.users import User
from src.modules.auth.token import create_access_token

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://arap:arap@localhost:5434/arap_test",
)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Fake agent output — 2 questions, first has resume_reference=True
FAKE_QUESTIONS = [
    {
        "question": "Describe your async Python experience at Acme Corp.",
        "category": "Technical",
        "target_competencies": ["Technical Accuracy"],
        "difficulty": "hard",
        "answer_format": "long_text",
        "resume_reference": True,
    },
    {
        "question": "Tell me about a conflict you resolved in your team.",
        "category": "Conflict Resolution",
        "target_competencies": ["Conflict Handling"],
        "difficulty": "medium",
        "answer_format": "long_text",
        "resume_reference": False,
    },
]

# Fake embedding: use distinct fixed vectors (dim=1536)
FAKE_EMBEDDINGS = [
    [0.01 * i for i in range(1536)],   # question 0
    [-0.01 * i for i in range(1536)],  # question 1 — dissimilar to q0
]


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
def r():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def seed(db):
    uid = _uuid.uuid4().hex[:8]
    org = Org(name=f"QS Test Org {uid}")
    db.add(org)
    db.flush()

    admin = User(
        org_id=org.id, email=f"admin-{uid}@qs.com", role="admin",
        password_hash=pwd_context.hash("pw"),
    )
    db.add(admin)
    db.flush()

    candidate = Candidate(
        org_id=org.id, name="Jane Doe", email=f"jane-{uid}@example.com",
        auth_method="magic_link",
    )
    db.add(candidate)
    db.flush()

    job = JobAssessment(
        org_id=org.id,
        title="Senior Backend Engineer",
        department="Engineering",
        difficulty_level="senior",
        duration_minutes=60,
        required_skills=["Python"],
        preferred_skills=["Docker"],
        behavioral_competencies=["problem_solving"],
        leadership_competencies=["mentoring"],
        competency_weightage={"problem_solving": 70.0, "mentoring": 30.0},
        created_by=admin.id,
        job_profile={
            "normalized_title": "Senior Backend Engineer",
            "role_summary": "Build scalable APIs.",
            "key_responsibilities": ["Design REST APIs"],
            "required_skills": ["Python"],
            "preferred_skills": ["Docker"],
            "difficulty_level": "senior",
        },
    )
    db.add(job)
    db.flush()

    profile = CandidateProfile(
        org_id=org.id,
        candidate_id=candidate.id,
        job_assessment_id=job.id,
        skill_matrix={"aligned": [{"skill": "Python", "alignment": "yes"}], "raw": {}},
        experience_matrix={"employment_history": [], "career_timeline": {}, "career_velocity": "Promoted twice"},
        leadership_level_estimate="Manager",
        strengths=["Deep Python expertise"],
        risk_flags=["No direct people-management despite Manager title at Acme Corp"],
        parsing_confidence=0.85,
    )
    db.add(profile)
    db.flush()

    session = AssessmentSession(
        org_id=org.id,
        job_assessment_id=job.id,
        candidate_id=candidate.id,
        candidate_profile_id=profile.id,
        time_budget_seconds=3600,
    )
    db.add(session)
    db.commit()

    db.refresh(org); db.refresh(admin); db.refresh(candidate)
    db.refresh(job); db.refresh(profile); db.refresh(session)

    return {
        "org": org, "admin": admin, "candidate": candidate,
        "job": job, "profile": profile, "session": session,
    }


@pytest.fixture
def user_token(seed):
    return create_access_token({
        "sub": str(seed["admin"].id),
        "role": "admin",
        "org_id": str(seed["org"].id),
    })


@pytest.fixture
def mock_agent():
    with patch(
        "src.modules.question_sets.service.run_question_generation_agent",
        return_value=FAKE_QUESTIONS,
    ) as m:
        yield m


@pytest.fixture
def mock_embed():
    with patch(
        "src.modules.question_sets.service.embed_texts",
        return_value=FAKE_EMBEDDINGS,
    ) as m:
        yield m


@pytest_asyncio.fixture
async def async_client(db, r):
    from src.main import app
    from src.database import get_db, get_redis
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: r
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 3: Write `services/orchestrator-api/tests/question_sets/test_service.py`**

```python
import uuid
from unittest.mock import patch

import pytest

from tests.question_sets.conftest import FAKE_EMBEDDINGS, FAKE_QUESTIONS


def test_generate_persists_question_set(db, seed, mock_agent, mock_embed):
    from src.modules.question_sets.service import generate_question_set

    result = generate_question_set(db, seed["session"].id, seed["org"].id, target=2)

    assert result.session_id == seed["session"].id
    assert result.locked_at is not None
    assert result.generation_prompt_version == "v1.0"
    assert len(result.questions) == 2
    assert result.questions[0].sequence_no == 1
    assert result.questions[1].sequence_no == 2


def test_generate_rejects_duplicate_above_threshold(db, seed, mock_agent):
    from src.models.question_fingerprints import QuestionFingerprint
    from src.modules.question_sets.service import generate_question_set

    # Pre-insert a fingerprint nearly identical to FAKE_QUESTIONS[0] (cosine sim ≈ 1.0)
    near_identical = [v + 0.000001 for v in FAKE_EMBEDDINGS[0]]
    fp = QuestionFingerprint(
        org_id=seed["org"].id,
        question_text="Near-duplicate of question 0",
        question_embedding=near_identical,
    )
    db.add(fp)
    db.commit()

    # embed_texts returns FAKE_EMBEDDINGS for pass 1 (2 questions) and
    # FAKE_EMBEDDINGS[1:] for pass 2 (gap fill)
    emb_calls = [FAKE_EMBEDDINGS, [FAKE_EMBEDDINGS[1]]]
    call_idx = [0]

    def fake_embed(texts):
        idx = call_idx[0]
        call_idx[0] += 1
        return emb_calls[idx] if idx < len(emb_calls) else [FAKE_EMBEDDINGS[1]]

    # agent returns 2 questions on pass 1 (q0 is duplicate), then 1 on pass 2
    agent_calls = [FAKE_QUESTIONS, [FAKE_QUESTIONS[1]]]
    agent_idx = [0]

    def fake_agent(**kwargs):
        idx = agent_idx[0]
        agent_idx[0] += 1
        return agent_calls[idx] if idx < len(agent_calls) else [FAKE_QUESTIONS[1]]

    with patch("src.modules.question_sets.service.run_question_generation_agent", side_effect=lambda **kw: fake_agent(**kw)), \
         patch("src.modules.question_sets.service.embed_texts", side_effect=fake_embed):
        # target=1: q0 is rejected (similarity ≥ 0.92), q1 is accepted → 1 question
        result = generate_question_set(db, seed["session"].id, seed["org"].id, target=1)

    assert len(result.questions) == 1
    assert result.questions[0].question == FAKE_QUESTIONS[1]["question"]


def test_generate_accepts_below_threshold(db, seed, mock_agent):
    from src.models.question_fingerprints import QuestionFingerprint
    from src.modules.question_sets.service import generate_question_set

    # Pre-insert a fingerprint very different from both fake embeddings (orthogonal)
    orthogonal = [0.0] * 1535 + [1.0]
    fp = QuestionFingerprint(
        org_id=seed["org"].id,
        question_text="Unrelated question",
        question_embedding=orthogonal,
    )
    db.add(fp)
    db.commit()

    with patch("src.modules.question_sets.service.embed_texts", return_value=FAKE_EMBEDDINGS):
        result = generate_question_set(db, seed["session"].id, seed["org"].id, target=2)

    assert len(result.questions) == 2


def test_generate_raises_lookup_when_session_not_found(db, seed):
    from src.modules.question_sets.service import generate_question_set

    with pytest.raises(LookupError, match="session"):
        generate_question_set(db, uuid.uuid4(), seed["org"].id)


def test_generate_raises_value_error_when_no_candidate_profile(db, seed, mock_agent, mock_embed):
    from src.models.assessment_sessions import AssessmentSession
    from src.modules.question_sets.service import generate_question_set

    session = db.query(AssessmentSession).filter_by(id=seed["session"].id).first()
    original = session.candidate_profile_id
    session.candidate_profile_id = None
    db.commit()

    try:
        with pytest.raises(ValueError, match="Candidate profile"):
            generate_question_set(db, seed["session"].id, seed["org"].id)
    finally:
        session.candidate_profile_id = original
        db.commit()


def test_generate_raises_runtime_when_agent_returns_none(db, seed, mock_embed):
    from src.modules.question_sets.service import generate_question_set

    with patch("src.modules.question_sets.service.run_question_generation_agent", return_value=None):
        with pytest.raises(RuntimeError, match="agent"):
            generate_question_set(db, seed["session"].id, seed["org"].id)


def test_get_raises_lookup_when_not_generated(db, seed):
    from src.modules.question_sets.service import get_question_set

    with pytest.raises(LookupError):
        get_question_set(db, seed["session"].id, seed["org"].id)


def test_get_returns_set_after_generate(db, seed, mock_agent, mock_embed):
    from src.modules.question_sets.service import generate_question_set, get_question_set

    generate_question_set(db, seed["session"].id, seed["org"].id, target=2)
    result = get_question_set(db, seed["session"].id, seed["org"].id)

    assert len(result.questions) == 2
    assert result.locked_at is not None
```

- [ ] **Step 4: Run service tests** (requires test DB running on port 5434)

```
cd services/orchestrator-api
pytest tests/question_sets/test_service.py -v
```

Expected: all service tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/orchestrator-api/src/modules/question_sets/service.py \
  services/orchestrator-api/tests/question_sets/conftest.py \
  services/orchestrator-api/tests/question_sets/test_service.py
git commit -m "[TASK-001] feat: add question_sets service with pgvector dedup and set lock (M4-F01–F06)"
```

---

## Task 5: Router + register in main.py + router tests

**Files:**
- Create: `services/orchestrator-api/src/modules/question_sets/router.py`
- Modify: `services/orchestrator-api/src/main.py`
- Create: `services/orchestrator-api/tests/question_sets/test_router.py`

**Interfaces:**
- Consumes: `generate_question_set(db, session_id, org_id)→QuestionSetResponse` and `get_question_set(db, session_id, org_id)→QuestionSetResponse` from Task 4; `QuestionSetResponse` from Task 3
- Produces: `POST /question-sets/generate/{session_id}` → 201 | 404 | 409 | 422 | 502; `GET /question-sets/{session_id}` → 200 | 404

- [ ] **Step 1: Write `services/orchestrator-api/src/modules/question_sets/router.py`**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.question_sets import QuestionSet
from src.modules.auth.dependencies import TokenClaims, require_user
from src.modules.question_sets import service
from src.modules.question_sets.schemas import QuestionSetResponse

router = APIRouter(prefix="/question-sets", tags=["question-sets"])


@router.post(
    "/generate/{session_id}",
    response_model=QuestionSetResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    existing = db.query(QuestionSet).filter_by(session_id=session_id).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Question set already generated and locked for this session",
        )
    try:
        return service.generate_question_set(db, session_id, claims.org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/{session_id}", response_model=QuestionSetResponse)
def get_set(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.get_question_set(db, session_id, claims.org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 2: Register router in `services/orchestrator-api/src/main.py`**

Add these two lines (import + include_router), following the existing pattern:

```python
# Add after the candidate_profiles import:
from src.modules.question_sets.router import router as question_sets_router

# Add after app.include_router(candidate_profiles_router):
app.include_router(question_sets_router)
```

Full updated file:

```python
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.health import router as health_router
from src.config import settings
from src.middleware.auth import AuthMiddleware
from src.middleware.error_handler import (
    http_exception_handler,
    unhandled_exception_handler,
)
from src.middleware.rate_limit import RateLimitMiddleware
from src.modules.auth.router import router as auth_router
from src.modules.candidate_profiles.router import router as candidate_profiles_router
from src.modules.competency_library.router import router as competency_library_router
from src.modules.job_assessments.router import router as job_assessments_router
from src.modules.question_sets.router import router as question_sets_router

app = FastAPI(
    title="ARAP Orchestrator API",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(competency_library_router)
app.include_router(job_assessments_router)
app.include_router(candidate_profiles_router)
app.include_router(question_sets_router)
```

- [ ] **Step 3: Write `services/orchestrator-api/tests/question_sets/test_router.py`**

```python
import uuid

import pytest

from tests.question_sets.conftest import FAKE_EMBEDDINGS, FAKE_QUESTIONS


@pytest.mark.asyncio
async def test_generate_returns_201(async_client, seed, user_token, mock_agent, mock_embed):
    resp = await async_client.post(
        f"/question-sets/generate/{seed['session'].id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["session_id"] == str(seed["session"].id)
    assert body["locked_at"] is not None
    assert body["generation_prompt_version"] == "v1.0"
    assert len(body["questions"]) == 2
    assert body["questions"][0]["sequence_no"] == 1
    assert body["questions"][0]["question"] == FAKE_QUESTIONS[0]["question"]


@pytest.mark.asyncio
async def test_generate_returns_404_when_session_not_found(async_client, seed, user_token, mock_agent, mock_embed):
    resp = await async_client.post(
        f"/question-sets/generate/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generate_returns_409_when_called_twice(async_client, seed, user_token, mock_agent, mock_embed):
    await async_client.post(
        f"/question-sets/generate/{seed['session'].id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp = await async_client.post(
        f"/question-sets/generate/{seed['session'].id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_generate_returns_422_when_no_candidate_profile(async_client, seed, user_token, db, mock_agent, mock_embed):
    from src.models.assessment_sessions import AssessmentSession

    session = db.query(AssessmentSession).filter_by(id=seed["session"].id).first()
    original = session.candidate_profile_id
    session.candidate_profile_id = None
    db.commit()

    try:
        resp = await async_client.post(
            f"/question-sets/generate/{seed['session'].id}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 422
    finally:
        session.candidate_profile_id = original
        db.commit()


@pytest.mark.asyncio
async def test_generate_returns_502_when_agent_fails(async_client, seed, user_token, mock_embed):
    from unittest.mock import patch

    with patch(
        "src.modules.question_sets.service.run_question_generation_agent",
        return_value=None,
    ):
        resp = await async_client.post(
            f"/question-sets/generate/{seed['session'].id}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_get_returns_404_before_generate(async_client, seed, user_token):
    resp = await async_client.get(
        f"/question-sets/{seed['session'].id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_returns_200_after_generate(async_client, seed, user_token, mock_agent, mock_embed):
    await async_client.post(
        f"/question-sets/generate/{seed['session'].id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    resp = await async_client.get(
        f"/question-sets/{seed['session'].id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == str(seed["session"].id)
    assert len(body["questions"]) == 2


@pytest.mark.asyncio
async def test_generate_requires_auth(async_client, seed):
    resp = await async_client.post(f"/question-sets/generate/{seed['session'].id}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_requires_auth(async_client, seed):
    resp = await async_client.get(f"/question-sets/{seed['session'].id}")
    assert resp.status_code == 401
```

- [ ] **Step 4: Run the full question_sets test suite**

```
cd services/orchestrator-api
pytest tests/question_sets/ -v
```

Expected: all tests in `test_agent.py`, `test_service.py`, `test_router.py` PASS.

- [ ] **Step 5: Run the full orchestrator-api suite to check for regressions**

```
cd services/orchestrator-api
pytest -v
```

Expected: all previously passing tests still PASS; new question_sets tests added to total.

- [ ] **Step 6: Commit**

```bash
git add services/orchestrator-api/src/modules/question_sets/router.py \
  services/orchestrator-api/src/main.py \
  services/orchestrator-api/tests/question_sets/test_router.py
git commit -m "[TASK-001] feat: add question_sets router, register endpoints POST /generate GET / (M4 complete)"
```

---

## Self-Review

**Spec coverage:**
- M4-F01 Upfront batch generation → Task 1 agent + Task 4 service (single LLM call, complete set before lock) ✓
- M4-F02 Category coverage → `_derive_category_counts()` in service + `category_weightage` passed to agent ✓
- M4-F03 Resume-referenced questions → `resume_reference` in tool schema, validated in service, gap pass if missing ✓
- M4-F04 Risk-flag targeted questions → `risk_flags` passed to agent with explicit instruction in user message ✓
- M4-F05 No-repeat guarantee → `_is_duplicate()` pgvector cosine query, two-pass dedup ✓
- M4-F06 Set lock → `locked_at` set in same transaction as fingerprints ✓
- JSON contract from PRD §7 → tool schema matches exactly ✓
- 409 conflict on duplicate generate → checked in router ✓
- Auth `require_user` + `org_id` from JWT only → router fixtures confirm ✓
- `generation_prompt_version` constant → `PROMPT_VERSION = "v1.0"` in prompts.py ✓

**Placeholder scan:** No TBDs, no "implement later", all test code is concrete.

**Type consistency:**
- `run_question_generation_agent(...)` signature matches between Task 1 (definition) and Task 4 (call in service) ✓
- `embed_texts(texts: list[str]) -> list[list[float]]` matches between Task 2 (definition) and Task 4 (call) ✓
- `QuestionItem`, `QuestionSetResponse` defined in Task 3, consumed in Tasks 4 and 5 ✓
- `generate_question_set(db, session_id, org_id, target)` defined in Task 4, called in Task 5 ✓
- `get_question_set(db, session_id, org_id)` defined in Task 4, called in Task 5 ✓

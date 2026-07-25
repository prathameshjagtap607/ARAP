# M8 Fraud & Integrity Detection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement M8 Fraud & Integrity Detection (F01–F05) — statistical AI-generation heuristics, pgvector duplicate detection, LLM resume-consistency check, behavioral anomaly stub, and integrity summary compiled into every hiring report.

**Architecture:** Four check modules under `agents/integrity/checks/` each returning `list[FlagResult]`; `agent.py` orchestrates them, persists `integrity_flags` rows, and compiles `hiring_reports.integrity_summary`. A new `answer_corpus` table stores answer embeddings for org-scoped duplicate detection. The agent is wired into `evaluation_pipeline.py` after behavior inference.

**Tech Stack:** Python 3.11, SQLAlchemy 2.x, pgvector (HNSW), Alembic, Anthropic SDK (claude-sonnet-4-6) for F03, OpenAI SDK (text-embedding-3-small) for F01/F02, FastAPI, pytest.

## Global Constraints

- Never auto-reject based on integrity flags — `human_review_required` is advisory only (PRD §7 M8-F05)
- No protected characteristics in evidence fields (PRD §15)
- All checks are non-fatal — any failure logs and continues; missing integrity summary does not block report generation
- Model: `claude-sonnet-4-6` for F03 LLM call
- Embeddings: `text-embedding-3-small`, dimension 1536 (matches existing `question_fingerprints`)
- pgvector operator for cosine distance: `<=>` (cosine distance, so similarity = `1 - distance`)
- All agent tests mock `openai.OpenAI` and `anthropic.Anthropic` — no live API calls
- Commit format: `[TASK-002] <type>: <what>`
- Run tests from `services/orchestrator-api/` with `python -m pytest <path> -v`

---

## File Map

**New files:**
- `services/orchestrator-api/src/models/answer_corpus.py` — SQLAlchemy ORM model
- `services/orchestrator-api/migrations/versions/0004_answer_corpus.py` — Alembic migration
- `agents/integrity/__init__.py` — empty
- `agents/integrity/checks/__init__.py` — empty
- `agents/integrity/checks/ai_generated.py` — F01 statistical heuristics
- `agents/integrity/checks/duplicate.py` — F02 pgvector ANN + corpus ingest
- `agents/integrity/checks/resume_consistency.py` — F03 LLM cross-check
- `agents/integrity/checks/behavioral_anomaly.py` — F04 stub
- `agents/integrity/agent.py` — orchestrator + `_compile_integrity_summary`
- `agents/integrity/tests/__init__.py` — empty
- `agents/integrity/tests/test_ai_generated.py`
- `agents/integrity/tests/test_duplicate.py`
- `agents/integrity/tests/test_resume_consistency.py`
- `agents/integrity/tests/test_agent.py`
- `services/orchestrator-api/src/modules/integrity/__init__.py` — empty
- `services/orchestrator-api/src/modules/integrity/schemas.py`
- `services/orchestrator-api/src/modules/integrity/service.py`
- `services/orchestrator-api/src/modules/integrity/router.py`

**Modified files:**
- `services/orchestrator-api/src/models/__init__.py` — add `AnswerCorpus`
- `agents/evaluation/pipeline.py` — add `_run_integrity_checks` helper + call
- `services/orchestrator-api/src/main.py` — register integrity router

---

### Task 1: `answer_corpus` model + Alembic migration

**Files:**
- Create: `services/orchestrator-api/src/models/answer_corpus.py`
- Create: `services/orchestrator-api/migrations/versions/0004_answer_corpus.py`
- Modify: `services/orchestrator-api/src/models/__init__.py`

**Interfaces:**
- Produces: `AnswerCorpus` ORM class importable as `from src.models.answer_corpus import AnswerCorpus`; columns: `id`, `org_id`, `session_id`, `session_question_id`, `answer_embedding` (Vector 1536), `created_at`

- [ ] **Step 1: Write `answer_corpus.py`**

```python
# services/orchestrator-api/src/models/answer_corpus.py
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .question_fingerprints import EMBEDDING_DIM


class AnswerCorpus(Base):
    __tablename__ = "answer_corpus"
    __table_args__ = (
        UniqueConstraint("session_question_id", name="uq_answer_corpus_session_question_id"),
        Index(
            "idx_answer_corpus_embedding",
            "answer_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"answer_embedding": "vector_cosine_ops"},
        ),
        Index("idx_answer_corpus_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_sessions.id"), nullable=False
    )
    session_question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("session_questions.id"), nullable=False
    )
    answer_embedding: Mapped[list] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 2: Write migration `0004_answer_corpus.py`**

```python
# services/orchestrator-api/migrations/versions/0004_answer_corpus.py
"""add answer_corpus table for duplicate answer detection

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-25
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "answer_corpus",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("session_question_id", sa.UUID(), nullable=False),
        sa.Column("answer_embedding", Vector(1536), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["assessment_sessions.id"]),
        sa.ForeignKeyConstraint(["session_question_id"], ["session_questions.id"]),
        sa.UniqueConstraint(
            "session_question_id", name="uq_answer_corpus_session_question_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_answer_corpus_embedding",
        "answer_corpus",
        ["answer_embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"answer_embedding": "vector_cosine_ops"},
    )
    op.create_index("idx_answer_corpus_org_id", "answer_corpus", ["org_id"])
    op.execute(
        """
        ALTER TABLE answer_corpus ENABLE ROW LEVEL SECURITY;
        CREATE POLICY answer_corpus_org_isolation ON answer_corpus
            USING (org_id = current_setting('app.current_org_id')::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS answer_corpus_org_isolation ON answer_corpus;")
    op.drop_index("idx_answer_corpus_org_id", table_name="answer_corpus")
    op.drop_index("idx_answer_corpus_embedding", table_name="answer_corpus")
    op.drop_table("answer_corpus")
```

- [ ] **Step 3: Add `AnswerCorpus` to `src/models/__init__.py`**

Add this import line after the existing imports (alphabetical order, after `AssessmentSession`):

```python
from .answer_corpus import AnswerCorpus
```

Add `"AnswerCorpus"` to `__all__`.

- [ ] **Step 4: Run migration to verify it applies cleanly**

```bash
cd services/orchestrator-api
alembic upgrade head
```

Expected: no errors, `answer_corpus` table visible in DB.

- [ ] **Step 5: Run existing model tests to confirm no regression**

```bash
cd services/orchestrator-api
python -m pytest tests/models/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add services/orchestrator-api/src/models/answer_corpus.py \
        services/orchestrator-api/migrations/versions/0004_answer_corpus.py \
        services/orchestrator-api/src/models/__init__.py
git commit -m "[TASK-002] feat(integrity): answer_corpus model and migration 0004"
```

---

### Task 2: F01 — AI-Generated/Scripted Detection

**Files:**
- Create: `agents/integrity/__init__.py`
- Create: `agents/integrity/checks/__init__.py`
- Create: `agents/integrity/checks/ai_generated.py`
- Create: `agents/integrity/tests/__init__.py`
- Create: `agents/integrity/tests/test_ai_generated.py`

**Interfaces:**
- Consumes: list of `SessionQuestion` objects (attributes: `answer_text`, `answer_format`, `answered_at`, `sequence_no`, `id`), `AssessmentSession` object (attribute: `started_at`)
- Produces: `check_ai_generated(questions, session) -> list[FlagResult]` where `FlagResult` is the dataclass defined in this file

- [ ] **Step 1: Write the failing tests**

```python
# agents/integrity/tests/test_ai_generated.py
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from agents.integrity.checks.ai_generated import FlagResult, check_ai_generated


def _make_session(started_at=None):
    s = object.__new__(object)
    object.__setattr__(s, "__class__", type("Session", (), {})())
    class Sess:
        pass
    sess = Sess()
    sess.started_at = started_at or datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    return sess


def _make_q(seq, text, fmt="long_text", answered_offset_s=300):
    class Q:
        pass
    q = Q()
    q.id = uuid.uuid4()
    q.sequence_no = seq
    q.answer_text = text
    q.answer_format = fmt
    q.answered_at = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC) + timedelta(seconds=answered_offset_s)
    return q


# Case 1: Fewer than 2 long_text questions → skip, no flags
def test_too_few_long_text_skips():
    session = _make_session()
    qs = [_make_q(1, "Short answer.", fmt="short_text")]
    result = check_ai_generated(qs, session)
    assert result == []


# Case 2: Varied answers (different sentence counts, reasonable latency) → no flag
def test_varied_answers_no_flag():
    session = _make_session()
    qs = [
        _make_q(1, "I worked at Acme for three years. I built the billing pipeline. It handled $2M/day.", fmt="long_text", answered_offset_s=600),
        _make_q(2, "Yeah, I know Python well. I have used it since college. Sometimes I use Go.", fmt="long_text", answered_offset_s=900),
        _make_q(3, "My biggest challenge was a database migration. We had downtime risk. I solved it by staging the cutover. Then monitored for two days.", fmt="long_text", answered_offset_s=1200),
    ]
    result = check_ai_generated(qs, session)
    assert result == []


# Case 3: Uniform structure only (identical sentence count + all prose, reasonable latency) → flag low
def test_structural_uniformity_flag_low():
    session = _make_session()
    # All answers: exactly 2 sentences, all prose, within normal latency
    uniform_answer = "This is sentence one. This is sentence two."
    qs = [
        _make_q(i, uniform_answer, fmt="long_text", answered_offset_s=300 * i)
        for i in range(1, 4)
    ]
    with patch("agents.integrity.checks.ai_generated._embed_texts_safe", return_value=None):
        result = check_ai_generated(qs, session)
    assert len(result) == 1
    assert result[0].flag_type == "ai_generated"
    assert result[0].severity == "low"
    assert result[0].session_question_id is None


# Case 4: Latency anomaly only (answer typed impossibly fast) → flag low
def test_latency_anomaly_flag_low():
    session = _make_session()
    # 500 chars in 10 seconds = 50 cps (threshold is 20)
    long_text = "x" * 500
    qs = [
        _make_q(1, long_text, fmt="long_text", answered_offset_s=10),
        _make_q(2, "Normal answer here. I took my time. It was good.", fmt="long_text", answered_offset_s=600),
    ]
    with patch("agents.integrity.checks.ai_generated._embed_texts_safe", return_value=None):
        result = check_ai_generated(qs, session)
    assert len(result) == 1
    assert result[0].severity == "low"
    assert "latency_max" in result[0].evidence


# Case 5: Two signals triggered → flag medium
def test_two_signals_medium():
    session = _make_session()
    uniform_answer = "This is sentence one. This is sentence two."
    long_text_fast = "x" * 500
    qs = [
        _make_q(1, uniform_answer, fmt="long_text", answered_offset_s=10),   # latency anomaly
        _make_q(2, uniform_answer, fmt="long_text", answered_offset_s=300),
        _make_q(3, uniform_answer, fmt="long_text", answered_offset_s=600),  # structural uniform
    ]
    with patch("agents.integrity.checks.ai_generated._embed_texts_safe", return_value=None):
        result = check_ai_generated(qs, session)
    assert len(result) == 1
    assert result[0].severity == "medium"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd services/orchestrator-api
python -m pytest ../agents/integrity/tests/test_ai_generated.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` (module doesn't exist yet).

- [ ] **Step 3: Create empty `__init__.py` files**

Create these three empty files:
- `agents/integrity/__init__.py`
- `agents/integrity/checks/__init__.py`
- `agents/integrity/tests/__init__.py`

- [ ] **Step 4: Write `agents/integrity/checks/ai_generated.py`**

```python
# agents/integrity/checks/ai_generated.py
import math
import statistics
import uuid
from dataclasses import dataclass
from datetime import UTC

_LATENCY_THRESHOLD_CPS = 20.0
_STRUCTURAL_STD_THRESHOLD = 1.5
_PHRASING_SIM_THRESHOLD = 0.30


@dataclass
class FlagResult:
    flag_type: str
    severity: str
    evidence: str
    session_question_id: uuid.UUID | None


def check_ai_generated(questions: list, session) -> list[FlagResult]:
    long_qs = [q for q in questions if q.answer_format == "long_text" and q.answer_text]
    if len(long_qs) < 2:
        return []

    signals: list[str] = []
    stats_parts: list[str] = []

    # Signal 1: structural uniformity
    sentence_counts = [_count_sentences(q.answer_text) for q in long_qs]
    std_dev = statistics.pstdev(sentence_counts)
    all_same_format = all(_is_bulleted(q.answer_text) for q in long_qs) or all(
        not _is_bulleted(q.answer_text) for q in long_qs
    )
    stats_parts.append(f"structural_std={std_dev:.2f}")
    if std_dev < _STRUCTURAL_STD_THRESHOLD and all_same_format:
        signals.append("structural_uniformity")

    # Signal 2: latency anomaly
    started = session.started_at
    if started and started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    max_cps = 0.0
    if started:
        for q in long_qs:
            answered = q.answered_at
            if answered is None or not q.answer_text:
                continue
            if answered.tzinfo is None:
                answered = answered.replace(tzinfo=UTC)
            elapsed = (answered - started).total_seconds()
            if elapsed > 0:
                cps = len(q.answer_text) / elapsed
                max_cps = max(max_cps, cps)
    stats_parts.append(f"latency_max={max_cps:.1f}cps")
    if max_cps > _LATENCY_THRESHOLD_CPS:
        signals.append("latency_anomaly")

    # Signal 3: phrasing divergence (best-effort — skipped if embedding fails)
    all_answered = [q.answer_text for q in questions if q.answer_text]
    if all_answered:
        formal_texts = [q.answer_text for q in long_qs]
        casual = min(all_answered, key=len)
        embeddings = _embed_texts_safe(formal_texts + [casual])
        if embeddings is not None:
            formal_embs = embeddings[: len(formal_texts)]
            casual_emb = embeddings[-1]
            sims = [_cosine(fe, casual_emb) for fe in formal_embs]
            mean_sim = sum(sims) / len(sims)
            stats_parts.append(f"phrasing_sim={mean_sim:.2f}")
            if mean_sim < _PHRASING_SIM_THRESHOLD:
                signals.append("phrasing_divergence")

    if not signals:
        return []

    n = len(signals)
    severity = "low" if n == 1 else ("medium" if n == 2 else "high")
    return [
        FlagResult(
            flag_type="ai_generated",
            severity=severity,
            evidence=", ".join(stats_parts),
            session_question_id=None,
        )
    ]


def _count_sentences(text: str) -> int:
    return max(1, text.count(".") + text.count("!") + text.count("?"))


def _is_bulleted(text: str) -> bool:
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return False
    bullet_lines = sum(1 for ln in lines if ln.strip().startswith(("-", "*", "•", "–")))
    return bullet_lines / len(lines) >= 0.5


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _embed_texts_safe(texts: list[str]) -> list[list[float]] | None:
    try:
        from src.modules.question_sets.embeddings import embed_texts
        return embed_texts(texts)
    except Exception:
        return None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd services/orchestrator-api
python -m pytest ../agents/integrity/tests/test_ai_generated.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add agents/integrity/__init__.py \
        agents/integrity/checks/__init__.py \
        agents/integrity/checks/ai_generated.py \
        agents/integrity/tests/__init__.py \
        agents/integrity/tests/test_ai_generated.py
git commit -m "[TASK-002] feat(integrity): F01 ai_generated statistical check"
```

---

### Task 3: F02 — Duplicate/Near-Duplicate Detection

**Files:**
- Create: `agents/integrity/checks/duplicate.py`
- Create: `agents/integrity/tests/test_duplicate.py`

**Interfaces:**
- Consumes: `FlagResult` from `agents.integrity.checks.ai_generated`
- Produces:
  - `check_duplicate(questions, session, db) -> list[FlagResult]` — flags per matching answer
  - `ingest_corpus(questions, session, db) -> None` — bulk insert into `answer_corpus`

- [ ] **Step 1: Write failing tests**

```python
# agents/integrity/tests/test_duplicate.py
import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest

# Mock ORM models before importing the module under test
_FAKE_ORM = {
    "src": MagicMock(),
    "src.models": MagicMock(),
    "src.models.answer_corpus": MagicMock(),
    "src.modules": MagicMock(),
    "src.modules.question_sets": MagicMock(),
    "src.modules.question_sets.embeddings": MagicMock(),
}

_ORG_ID = uuid.uuid4()
_SESSION_ID = uuid.uuid4()


def _make_session():
    s = MagicMock()
    s.org_id = _ORG_ID
    s.id = _SESSION_ID
    return s


def _make_q(text="Some answer text here.", fmt="long_text"):
    q = MagicMock()
    q.id = uuid.uuid4()
    q.answer_text = text
    q.answer_format = fmt
    return q


def _make_db(similarity_rows):
    """similarity_rows: list of (session_question_id, similarity) tuples returned by ANN query."""
    db = MagicMock()
    execute_result = MagicMock()
    execute_result.fetchall.return_value = [
        MagicMock(session_question_id=r[0], similarity=r[1])
        for r in similarity_rows
    ]
    db.execute.return_value = execute_result
    return db


# Case 1: similarity >= 0.92 → flag high
def test_high_similarity_flag():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.checks.duplicate import check_duplicate

        other_sq_id = uuid.uuid4()
        questions = [_make_q()]
        session = _make_session()
        db = _make_db([(other_sq_id, 0.95)])

        fake_embed = MagicMock(return_value=[[0.1] * 1536])
        with patch("agents.integrity.checks.duplicate._embed_answers", fake_embed):
            result = check_duplicate(questions, session, db)

    assert len(result) == 1
    assert result[0].flag_type == "duplicate_answer"
    assert result[0].severity == "high"
    assert "0.950" in result[0].evidence
    assert result[0].session_question_id == questions[0].id


# Case 2: similarity 0.87 → flag medium
def test_medium_similarity_flag():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.checks.duplicate import check_duplicate

        other_sq_id = uuid.uuid4()
        questions = [_make_q()]
        session = _make_session()
        db = _make_db([(other_sq_id, 0.87)])

        with patch("agents.integrity.checks.duplicate._embed_answers", return_value=[[0.1] * 1536]):
            result = check_duplicate(questions, session, db)

    assert len(result) == 1
    assert result[0].severity == "medium"


# Case 3: similarity 0.80 → no flag
def test_low_similarity_no_flag():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.checks.duplicate import check_duplicate

        other_sq_id = uuid.uuid4()
        questions = [_make_q()]
        session = _make_session()
        db = _make_db([(other_sq_id, 0.80)])

        with patch("agents.integrity.checks.duplicate._embed_answers", return_value=[[0.1] * 1536]):
            result = check_duplicate(questions, session, db)

    assert result == []


# Case 4: ingest_corpus bulk-inserts one row per answered question
def test_ingest_corpus_inserts_rows():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.checks.duplicate import ingest_corpus

        questions = [_make_q(), _make_q()]
        session = _make_session()
        db = MagicMock()
        embeddings = [[0.1] * 1536, [0.2] * 1536]

        ingest_corpus(questions, session, db, embeddings)

    assert db.add.call_count == 2
    db.flush.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd services/orchestrator-api
python -m pytest ../agents/integrity/tests/test_duplicate.py -v
```

Expected: `ImportError` — module not found.

- [ ] **Step 3: Write `agents/integrity/checks/duplicate.py`**

```python
# agents/integrity/checks/duplicate.py
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from agents.integrity.checks.ai_generated import FlagResult

_HIGH_THRESHOLD = 0.92
_MEDIUM_THRESHOLD = 0.85


def check_duplicate(questions: list, session, db: Session) -> list[FlagResult]:
    answered = [q for q in questions if q.answer_text]
    if not answered:
        return []

    embeddings = _embed_answers([q.answer_text for q in answered])
    flags: list[FlagResult] = []

    for q, embedding in zip(answered, embeddings):
        rows = db.execute(
            text(
                "SELECT session_question_id, "
                "1 - (answer_embedding <=> CAST(:vec AS vector)) AS similarity "
                "FROM answer_corpus "
                "WHERE org_id = :org_id "
                "ORDER BY answer_embedding <=> CAST(:vec AS vector) "
                "LIMIT 3"
            ),
            {"vec": str(embedding), "org_id": str(session.org_id)},
        ).fetchall()

        for row in rows:
            sim: float = row.similarity
            if sim >= _HIGH_THRESHOLD:
                severity = "high"
            elif sim >= _MEDIUM_THRESHOLD:
                severity = "medium"
            else:
                continue
            flags.append(
                FlagResult(
                    flag_type="duplicate_answer",
                    severity=severity,
                    evidence=(
                        f"cosine_similarity={sim:.3f} "
                        f"vs session_question_id={row.session_question_id}"
                    ),
                    session_question_id=q.id,
                )
            )
            break  # one flag per answer (highest match only)

    return flags


def ingest_corpus(
    questions: list,
    session,
    db: Session,
    embeddings: list[list[float]] | None = None,
) -> None:
    from src.models.answer_corpus import AnswerCorpus

    answered = [q for q in questions if q.answer_text]
    if not answered:
        return

    if embeddings is None:
        embeddings = _embed_answers([q.answer_text for q in answered])

    for q, embedding in zip(answered, embeddings):
        db.add(
            AnswerCorpus(
                org_id=session.org_id,
                session_id=session.id,
                session_question_id=q.id,
                answer_embedding=embedding,
            )
        )
    db.flush()


def _embed_answers(texts: list[str]) -> list[list[float]]:
    from src.modules.question_sets.embeddings import embed_texts
    return embed_texts(texts)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd services/orchestrator-api
python -m pytest ../agents/integrity/tests/test_duplicate.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add agents/integrity/checks/duplicate.py \
        agents/integrity/tests/test_duplicate.py
git commit -m "[TASK-002] feat(integrity): F02 duplicate answer detection with pgvector"
```

---

### Task 4: F03 — Resume-Answer Consistency

**Files:**
- Create: `agents/integrity/checks/resume_consistency.py`
- Create: `agents/integrity/tests/test_resume_consistency.py`

**Interfaces:**
- Consumes: `FlagResult` from `agents.integrity.checks.ai_generated`
- Produces: `check_resume_consistency(questions, candidate_profile) -> list[FlagResult]`

- [ ] **Step 1: Write failing tests**

```python
# agents/integrity/tests/test_resume_consistency.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd services/orchestrator-api
python -m pytest ../agents/integrity/tests/test_resume_consistency.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Write `agents/integrity/checks/resume_consistency.py`**

```python
# agents/integrity/checks/resume_consistency.py
import json

import anthropic

from agents.integrity.checks.ai_generated import FlagResult

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 2048

_SECTION_15_EXCLUSION = (
    "Do not infer, mention, score, or reference anything related to age, gender, "
    "race, ethnicity, religion, disability, national origin, physical appearance, "
    "or any other protected characteristic."
)

_SYSTEM_PROMPT = (
    "You are reviewing a job interview transcript for factual consistency with the "
    "candidate's parsed resume. Identify claims in the answers that contradict or are "
    "entirely absent from the resume data. Focus only on verifiable facts: named skills, "
    "technologies, job titles, company names, dates, and project outcomes. Do not flag "
    "unverifiable soft skills or subjective statements. "
    + _SECTION_15_EXCLUSION
)

_TOOL = {
    "name": "check_resume_consistency",
    "description": "Identify factual discrepancies between interview answers and parsed resume.",
    "input_schema": {
        "type": "object",
        "properties": {
            "discrepancies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "present_in_resume": {"type": "boolean"},
                        "conflict_type": {
                            "type": "string",
                            "enum": [
                                "skill_absent",
                                "experience_absent",
                                "timeline_conflict",
                                "minor_embellishment",
                            ],
                        },
                        "evidence": {"type": "string"},
                        "answer_sequence_no": {"type": "integer"},
                    },
                    "required": [
                        "claim",
                        "present_in_resume",
                        "conflict_type",
                        "evidence",
                        "answer_sequence_no",
                    ],
                },
            }
        },
        "required": ["discrepancies"],
    },
}

_SEVERITY_MAP = {
    "timeline_conflict": "high",
    "skill_absent": "medium",
    "experience_absent": "medium",
    "minor_embellishment": "low",
}


def check_resume_consistency(questions: list, candidate_profile) -> list[FlagResult]:
    long_qs = [q for q in questions if q.answer_format == "long_text" and q.answer_text]
    if not long_qs:
        return []

    transcript = "\n\n".join(
        f"Q{q.sequence_no}: {q.question.get('text', '')}\nA: {q.answer_text}"
        for q in long_qs
    )
    skill_matrix = json.dumps(dict(candidate_profile.skill_matrix or {}))
    experience_matrix = json.dumps(dict(candidate_profile.experience_matrix or {}))

    user_content = (
        f"INTERVIEW TRANSCRIPT:\n{transcript}\n\n"
        f"RESUME SKILL MATRIX:\n{skill_matrix}\n\n"
        f"RESUME EXPERIENCE MATRIX:\n{experience_matrix}"
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "check_resume_consistency"},
        messages=[{"role": "user", "content": user_content}],
    )
    tool_block = next(b for b in response.content if b.type == "tool_use")
    discrepancies = tool_block.input.get("discrepancies", [])

    seq_to_id = {q.sequence_no: q.id for q in questions}

    flags: list[FlagResult] = []
    for d in discrepancies:
        if d.get("present_in_resume"):
            continue
        conflict_type = d.get("conflict_type", "skill_absent")
        severity = _SEVERITY_MAP.get(conflict_type, "low")
        sq_id = seq_to_id.get(d.get("answer_sequence_no"))
        flags.append(
            FlagResult(
                flag_type="resume_inconsistency",
                severity=severity,
                evidence=d.get("evidence", ""),
                session_question_id=sq_id,
            )
        )

    return flags
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd services/orchestrator-api
python -m pytest ../agents/integrity/tests/test_resume_consistency.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add agents/integrity/checks/resume_consistency.py \
        agents/integrity/tests/test_resume_consistency.py
git commit -m "[TASK-002] feat(integrity): F03 resume-answer consistency check"
```

---

### Task 5: F04 stub + `agent.py` orchestrator + `test_agent.py`

**Files:**
- Create: `agents/integrity/checks/behavioral_anomaly.py`
- Create: `agents/integrity/agent.py`
- Create: `agents/integrity/tests/test_agent.py`

**Interfaces:**
- Consumes: `FlagResult` and `check_ai_generated` (Task 2), `check_duplicate` + `ingest_corpus` (Task 3), `check_resume_consistency` (Task 4)
- Produces: `run_integrity_checks(session_id, db_factory) -> None`

- [ ] **Step 1: Write `agents/integrity/checks/behavioral_anomaly.py`**

```python
# agents/integrity/checks/behavioral_anomaly.py
"""
Behavioral signal anomaly detection (M8-F04).
Deferred: requires voice/video session data (PRD §17).
When voice/video modalities ship, implement:
  - long pause detection
  - confidence mismatch between verbal and written responses
  - multi-speaker audio detection
All findings are flags for human review only — never automatic reject.
"""
import uuid

from agents.integrity.checks.ai_generated import FlagResult


def check_behavioral_anomalies(session_id: uuid.UUID, db) -> list[FlagResult]:
    return []
```

- [ ] **Step 2: Write failing tests for `agent.py`**

```python
# agents/integrity/tests/test_agent.py
import sys
import uuid
from unittest.mock import MagicMock, call, patch

import pytest

_SESSION_ID = uuid.uuid4()
_ORG_ID = uuid.uuid4()

_FAKE_ORM = {
    "src": MagicMock(),
    "src.models": MagicMock(),
    "src.models.assessment_sessions": MagicMock(),
    "src.models.candidate_profiles": MagicMock(),
    "src.models.hiring_reports": MagicMock(),
    "src.models.integrity_flags": MagicMock(),
    "src.models.answer_corpus": MagicMock(),
    "src.models.question_sets": MagicMock(),
    "src.models.session_questions": MagicMock(),
}


def _make_session(candidate_profile_id=None):
    s = MagicMock()
    s.org_id = _ORG_ID
    s.id = _SESSION_ID
    s.candidate_profile_id = candidate_profile_id
    return s


def _make_db(session_obj, qset_obj, questions, report_obj=None, profile_obj=None):
    db = MagicMock()
    flags_added = []

    def query_side_effect(model):
        q = MagicMock()
        model_name = str(model)
        if "AssessmentSession" in model_name:
            q.filter_by.return_value.first.return_value = session_obj
        elif "CandidateProfile" in model_name:
            q.filter_by.return_value.first.return_value = profile_obj
        elif "HiringReport" in model_name:
            q.filter_by.return_value.first.return_value = report_obj
        elif "IntegrityFlag" in model_name:
            pass
        elif "QuestionSet" in model_name:
            q.filter_by.return_value.first.return_value = qset_obj
        elif "SessionQuestion" in model_name:
            q.filter.return_value.order_by.return_value.all.return_value = questions
        return q

    db.query.side_effect = query_side_effect

    def add_side_effect(obj):
        flags_added.append(obj)

    db.add.side_effect = add_side_effect
    return db, flags_added


def _make_q(seq=1, fmt="long_text", answer="Some long answer text here."):
    q = MagicMock()
    q.id = uuid.uuid4()
    q.sequence_no = seq
    q.answer_text = answer
    q.answer_format = fmt
    q.question = {"text": f"Q{seq}?"}
    return q


# Case 1: happy path — F01 fires, integrity_summary written to report
def test_run_integrity_checks_happy_path():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.agent import run_integrity_checks
        from agents.integrity.checks.ai_generated import FlagResult

        session_obj = _make_session()
        qset_obj = MagicMock()
        qset_obj.id = uuid.uuid4()
        questions = [_make_q(i) for i in range(1, 4)]
        report_obj = MagicMock()
        report_obj.integrity_summary = {}

        db, flags_added = _make_db(session_obj, qset_obj, questions, report_obj=report_obj)

        fake_f01_flag = FlagResult("ai_generated", "medium", "structural_std=0.5", None)

        with (
            patch("agents.integrity.checks.ai_generated.check_ai_generated", return_value=[fake_f01_flag]),
            patch("agents.integrity.checks.duplicate.check_duplicate", return_value=[]),
            patch("agents.integrity.checks.duplicate.ingest_corpus"),
            patch("agents.integrity.checks.resume_consistency.check_resume_consistency", return_value=[]),
        ):
            run_integrity_checks(session_id=_SESSION_ID, db_factory=lambda: db)

    # One IntegrityFlag added
    assert len(flags_added) >= 1
    db.commit.assert_called()
    # integrity_summary written to report
    assert report_obj.integrity_summary["flagged_count"] == 1
    assert report_obj.integrity_summary["overall_risk"] == "low"
    assert "open_question" in report_obj.integrity_summary


# Case 2: LLM failure on F03 → non-fatal, F01 flag still written
def test_f03_failure_is_nonfatal():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.agent import run_integrity_checks
        from agents.integrity.checks.ai_generated import FlagResult

        session_obj = _make_session(candidate_profile_id=uuid.uuid4())
        qset_obj = MagicMock()
        qset_obj.id = uuid.uuid4()
        questions = [_make_q()]
        report_obj = MagicMock()
        report_obj.integrity_summary = {}

        db, flags_added = _make_db(session_obj, qset_obj, questions, report_obj=report_obj, profile_obj=MagicMock())

        fake_f01_flag = FlagResult("ai_generated", "low", "structural_std=1.0", None)

        with (
            patch("agents.integrity.checks.ai_generated.check_ai_generated", return_value=[fake_f01_flag]),
            patch("agents.integrity.checks.duplicate.check_duplicate", return_value=[]),
            patch("agents.integrity.checks.duplicate.ingest_corpus"),
            patch(
                "agents.integrity.checks.resume_consistency.check_resume_consistency",
                side_effect=RuntimeError("API timeout"),
            ),
        ):
            run_integrity_checks(session_id=_SESSION_ID, db_factory=lambda: db)

    assert len(flags_added) >= 1
    db.commit.assert_called()


# Case 3: zero answered questions → no flags, empty summary
def test_zero_answers_empty_summary():
    with patch.dict(sys.modules, _FAKE_ORM):
        from agents.integrity.agent import run_integrity_checks

        session_obj = _make_session()
        qset_obj = MagicMock()
        qset_obj.id = uuid.uuid4()
        report_obj = MagicMock()
        report_obj.integrity_summary = {}

        db, flags_added = _make_db(session_obj, qset_obj, [], report_obj=report_obj)

        run_integrity_checks(session_id=_SESSION_ID, db_factory=lambda: db)

    assert flags_added == []
    assert report_obj.integrity_summary["flagged_count"] == 0
    assert report_obj.integrity_summary["overall_risk"] == "low"
    assert report_obj.integrity_summary["human_review_required"] is False
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd services/orchestrator-api
python -m pytest ../agents/integrity/tests/test_agent.py -v
```

Expected: `ImportError`.

- [ ] **Step 4: Write `agents/integrity/agent.py`**

```python
# agents/integrity/agent.py
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from agents.integrity.checks.ai_generated import FlagResult, check_ai_generated
from agents.integrity.checks.behavioral_anomaly import check_behavioral_anomalies
from agents.integrity.checks.duplicate import check_duplicate, ingest_corpus
from agents.integrity.checks.resume_consistency import check_resume_consistency

logger = logging.getLogger(__name__)


def run_integrity_checks(
    session_id: uuid.UUID,
    db_factory: Callable[[], Session],
) -> None:
    from src.models.assessment_sessions import AssessmentSession
    from src.models.candidate_profiles import CandidateProfile
    from src.models.hiring_reports import HiringReport
    from src.models.integrity_flags import IntegrityFlag
    from src.models.question_sets import QuestionSet
    from src.models.session_questions import SessionQuestion

    db = db_factory()
    try:
        session = db.query(AssessmentSession).filter_by(id=session_id).first()
        if not session:
            logger.error("run_integrity_checks: session %s not found", session_id)
            return

        qset = db.query(QuestionSet).filter_by(session_id=session_id).first()
        if not qset:
            logger.error("run_integrity_checks: no question set for session %s", session_id)
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

        all_flags: list[FlagResult] = []

        # F01 — statistical heuristics
        try:
            all_flags.extend(check_ai_generated(questions, session))
        except Exception:
            logger.exception("F01 ai_generated check failed for session %s", session_id)

        # F02 — duplicate detection + corpus ingest
        try:
            dup_flags = check_duplicate(questions, session, db)
            all_flags.extend(dup_flags)
            ingest_corpus(questions, session, db)
        except Exception:
            logger.exception("F02 duplicate check failed for session %s", session_id)

        # F03 — resume consistency (skip if no candidate profile)
        try:
            candidate_profile = None
            if session.candidate_profile_id:
                candidate_profile = (
                    db.query(CandidateProfile)
                    .filter_by(id=session.candidate_profile_id)
                    .first()
                )
            if candidate_profile:
                all_flags.extend(check_resume_consistency(questions, candidate_profile))
            else:
                logger.info(
                    "run_integrity_checks: no candidate profile for session %s — skipping F03",
                    session_id,
                )
        except Exception:
            logger.exception("F03 resume_consistency check failed for session %s", session_id)

        # F04 — stub (always returns [])
        all_flags.extend(check_behavioral_anomalies(session_id, db))

        # Persist integrity_flags rows
        for flag in all_flags:
            db.add(
                IntegrityFlag(
                    org_id=session.org_id,
                    session_id=session_id,
                    session_question_id=flag.session_question_id,
                    flag_type=flag.flag_type,
                    severity=flag.severity,
                    evidence=flag.evidence,
                )
            )
        db.flush()

        # F05 — compile summary → hiring_reports.integrity_summary
        summary = _compile_integrity_summary(all_flags)
        report = db.query(HiringReport).filter_by(session_id=session_id).first()
        if report:
            report.integrity_summary = summary

        db.commit()
        logger.info(
            "run_integrity_checks: %d flag(s) written for session %s, risk=%s",
            len(all_flags),
            session_id,
            summary["overall_risk"],
        )

    except Exception:
        logger.exception("run_integrity_checks failed for session %s", session_id)
        db.rollback()
    finally:
        db.close()


def _compile_integrity_summary(flags: list[FlagResult]) -> dict:
    severities = [f.severity for f in flags]
    if "high" in severities:
        overall_risk = "high"
    elif severities.count("medium") >= 2:
        overall_risk = "medium"
    else:
        overall_risk = "low"

    human_review_required = overall_risk in ("high", "medium")

    return {
        "flagged_count": len(flags),
        "overall_risk": overall_risk,
        "human_review_required": human_review_required,
        "flags": [
            {
                "type": f.flag_type,
                "severity": f.severity,
                "evidence": f.evidence,
                "question_id": (
                    str(f.session_question_id) if f.session_question_id else None
                ),
            }
            for f in flags
        ],
        "open_question": (
            "Labeled validation set not available; recall >85% / FP <10% targets "
            "(PRD §3) cannot be verified — see TASK-002 Open Question #4."
        ),
    }
```

- [ ] **Step 5: Run all integrity tests**

```bash
cd services/orchestrator-api
python -m pytest ../agents/integrity/tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add agents/integrity/checks/behavioral_anomaly.py \
        agents/integrity/agent.py \
        agents/integrity/tests/test_agent.py
git commit -m "[TASK-002] feat(integrity): F04 stub + agent.py orchestrator with F05 summary"
```

---

### Task 6: Pipeline wiring

**Files:**
- Modify: `agents/evaluation/pipeline.py`

**Interfaces:**
- Consumes: `run_integrity_checks(session_id, db_factory)` from `agents.integrity.agent`

- [ ] **Step 1: Write a failing integration test for the pipeline wiring**

```python
# In agents/evaluation/tests/test_pipeline.py — add this test alongside existing ones
def test_pipeline_calls_integrity_checks(monkeypatch):
    """Verifies _run_integrity_checks is called after behavior inference."""
    import agents.evaluation.pipeline as pipeline_mod

    integrity_calls = []

    def fake_integrity(db, session_id):
        integrity_calls.append(session_id)

    monkeypatch.setattr(pipeline_mod, "_run_integrity_checks", fake_integrity)

    # Call the private helper directly to verify it delegates to run_integrity_checks
    from unittest.mock import MagicMock, patch
    import uuid

    sid = uuid.uuid4()
    db = MagicMock()

    with patch("agents.integrity.agent.run_integrity_checks") as mock_run:
        pipeline_mod._run_integrity_checks(db, sid)
        mock_run.assert_called_once_with(session_id=sid, db_factory=ANY)
```

Actually the above test is tightly coupled. Use a simpler check: after adding the helper, test that `_run_integrity_checks` calls `run_integrity_checks` and swallows exceptions:

```python
# agents/evaluation/tests/test_pipeline.py — add at the bottom

def test_run_integrity_checks_helper_delegates():
    import uuid
    from unittest.mock import MagicMock, patch

    db = MagicMock()
    sid = uuid.uuid4()

    with patch("agents.integrity.agent.run_integrity_checks") as mock_run:
        from agents.evaluation.pipeline import _run_integrity_checks
        _run_integrity_checks(db, sid)
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["session_id"] == sid


def test_run_integrity_checks_helper_swallows_exception():
    import uuid
    from unittest.mock import MagicMock, patch

    db = MagicMock()
    sid = uuid.uuid4()

    with patch("agents.integrity.agent.run_integrity_checks", side_effect=RuntimeError("boom")):
        from agents.evaluation.pipeline import _run_integrity_checks
        _run_integrity_checks(db, sid)  # must not raise
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
cd services/orchestrator-api
python -m pytest ../agents/evaluation/tests/test_pipeline.py::test_run_integrity_checks_helper_delegates \
                 ../agents/evaluation/tests/test_pipeline.py::test_run_integrity_checks_helper_swallows_exception -v
```

Expected: `AttributeError` — `_run_integrity_checks` not defined yet.

- [ ] **Step 3: Add `_run_integrity_checks` to `agents/evaluation/pipeline.py`**

Add this function at the bottom of `agents/evaluation/pipeline.py`:

```python
def _run_integrity_checks(db: Session, session_id: uuid.UUID) -> None:
    try:
        from agents.integrity.agent import run_integrity_checks
        run_integrity_checks(session_id=session_id, db_factory=lambda: db)
    except Exception:
        logger.exception("integrity checks failed for session %s", session_id)
```

Then in `evaluation_pipeline`, after the `_run_behavior_inference(db, session_id, job)` call, add:

```python
        _run_integrity_checks(db, session_id)
```

- [ ] **Step 4: Run pipeline tests to verify all pass**

```bash
cd services/orchestrator-api
python -m pytest ../agents/evaluation/tests/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add agents/evaluation/pipeline.py \
        agents/evaluation/tests/test_pipeline.py
git commit -m "[TASK-002] feat(integrity): wire integrity checks into evaluation pipeline"
```

---

### Task 7: Integrity module — service, router, schemas + register in `main.py`

**Files:**
- Create: `services/orchestrator-api/src/modules/integrity/__init__.py`
- Create: `services/orchestrator-api/src/modules/integrity/schemas.py`
- Create: `services/orchestrator-api/src/modules/integrity/service.py`
- Create: `services/orchestrator-api/src/modules/integrity/router.py`
- Modify: `services/orchestrator-api/src/main.py`

**Interfaces:**
- Produces: `GET /integrity/{session_id}` → `IntegritySummaryResponse`

- [ ] **Step 1: Write the failing service + router tests**

```python
# services/orchestrator-api/tests/integrity/__init__.py  (create empty)

# services/orchestrator-api/tests/integrity/conftest.py
import pytest
import uuid
from unittest.mock import MagicMock


@pytest.fixture
def org_id():
    return uuid.uuid4()


@pytest.fixture
def session_id():
    return uuid.uuid4()


@pytest.fixture
def mock_db():
    return MagicMock()
```

```python
# services/orchestrator-api/tests/integrity/test_service.py
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.modules.integrity.service import get_integrity_summary


def _make_session(session_id, org_id):
    s = MagicMock()
    s.id = session_id
    s.org_id = org_id
    return s


def _make_report(summary):
    r = MagicMock()
    r.integrity_summary = summary
    return r


def _make_flag(flag_type="ai_generated", severity="medium"):
    f = MagicMock()
    f.id = uuid.uuid4()
    f.flag_type = flag_type
    f.severity = severity
    f.evidence = "some evidence"
    f.session_question_id = None
    f.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    return f


def _make_db(session_obj, report_obj, flags):
    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        name = str(model)
        if "AssessmentSession" in name:
            q.filter_by.return_value.first.return_value = session_obj
        elif "HiringReport" in name:
            q.filter_by.return_value.first.return_value = report_obj
        elif "IntegrityFlag" in name:
            q.filter_by.return_value.order_by.return_value.all.return_value = flags
        return q

    db.query.side_effect = query_side_effect
    return db


def test_get_integrity_summary_returns_data(session_id, org_id):
    session_obj = _make_session(session_id, org_id)
    summary = {
        "flagged_count": 1,
        "overall_risk": "low",
        "human_review_required": False,
        "flags": [],
        "open_question": "test",
    }
    report_obj = _make_report(summary)
    flag = _make_flag()
    db = _make_db(session_obj, report_obj, [flag])

    result = get_integrity_summary(db, session_id, org_id)

    assert result.session_id == session_id
    assert result.flagged_count == 1
    assert result.overall_risk == "low"
    assert len(result.flags) == 1


def test_get_integrity_summary_session_not_found(session_id, org_id):
    db = _make_db(None, None, [])
    with pytest.raises(LookupError, match="assessment session not found"):
        get_integrity_summary(db, session_id, org_id)


def test_get_integrity_summary_report_not_ready(session_id, org_id):
    session_obj = _make_session(session_id, org_id)
    db = _make_db(session_obj, None, [])
    with pytest.raises(LookupError, match="not ready"):
        get_integrity_summary(db, session_id, org_id)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd services/orchestrator-api
python -m pytest tests/integrity/test_service.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create `src/modules/integrity/__init__.py`** (empty file)

- [ ] **Step 4: Write `src/modules/integrity/schemas.py`**

```python
# services/orchestrator-api/src/modules/integrity/schemas.py
import uuid
from datetime import datetime

from pydantic import BaseModel


class IntegrityFlagItem(BaseModel):
    id: uuid.UUID
    flag_type: str
    severity: str
    evidence: str
    session_question_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class IntegritySummaryResponse(BaseModel):
    session_id: uuid.UUID
    flagged_count: int
    overall_risk: str
    human_review_required: bool
    open_question: str | None
    flags: list[IntegrityFlagItem]
```

- [ ] **Step 5: Write `src/modules/integrity/service.py`**

```python
# services/orchestrator-api/src/modules/integrity/service.py
import uuid

from sqlalchemy.orm import Session

from src.models.assessment_sessions import AssessmentSession
from src.models.hiring_reports import HiringReport
from src.models.integrity_flags import IntegrityFlag
from src.modules.integrity.schemas import IntegrityFlagItem, IntegritySummaryResponse


def get_integrity_summary(
    db: Session, session_id: uuid.UUID, org_id: uuid.UUID
) -> IntegritySummaryResponse:
    session = db.query(AssessmentSession).filter_by(id=session_id, org_id=org_id).first()
    if not session:
        raise LookupError("assessment session not found")

    report = db.query(HiringReport).filter_by(session_id=session_id).first()
    if not report:
        raise LookupError("integrity summary not ready — report not generated yet")

    flags = (
        db.query(IntegrityFlag)
        .filter_by(session_id=session_id)
        .order_by(IntegrityFlag.created_at)
        .all()
    )

    summary = dict(report.integrity_summary or {})

    return IntegritySummaryResponse(
        session_id=session_id,
        flagged_count=summary.get("flagged_count", 0),
        overall_risk=summary.get("overall_risk", "low"),
        human_review_required=summary.get("human_review_required", False),
        open_question=summary.get("open_question"),
        flags=[IntegrityFlagItem.model_validate(f) for f in flags],
    )
```

- [ ] **Step 6: Write `src/modules/integrity/router.py`**

```python
# services/orchestrator-api/src/modules/integrity/router.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.modules.auth.dependencies import TokenClaims, require_user
from src.modules.integrity import service
from src.modules.integrity.schemas import IntegritySummaryResponse

router = APIRouter(prefix="/integrity", tags=["integrity"])


@router.get("/{session_id}", response_model=IntegritySummaryResponse)
def get_integrity_summary(
    session_id: uuid.UUID,
    claims: TokenClaims = Depends(require_user),
    db: Session = Depends(get_db),
):
    try:
        return service.get_integrity_summary(db, session_id, claims.org_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 7: Run service tests to verify they pass**

```bash
cd services/orchestrator-api
python -m pytest tests/integrity/test_service.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 8: Register the router in `src/main.py`**

Add the import after the existing router imports:

```python
from src.modules.integrity.router import router as integrity_router
```

Add after `app.include_router(reports_router)`:

```python
app.include_router(integrity_router)
```

- [ ] **Step 9: Run the full test suite to verify no regressions**

```bash
cd services/orchestrator-api
python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add services/orchestrator-api/src/modules/integrity/__init__.py \
        services/orchestrator-api/src/modules/integrity/schemas.py \
        services/orchestrator-api/src/modules/integrity/service.py \
        services/orchestrator-api/src/modules/integrity/router.py \
        services/orchestrator-api/src/main.py \
        services/orchestrator-api/tests/integrity/__init__.py \
        services/orchestrator-api/tests/integrity/conftest.py \
        services/orchestrator-api/tests/integrity/test_service.py
git commit -m "[TASK-002] feat(integrity): integrity module — service, router, schemas, main wiring"
```

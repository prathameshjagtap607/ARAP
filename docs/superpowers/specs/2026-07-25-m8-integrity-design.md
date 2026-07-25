# M8 Fraud & Integrity Detection — Design Spec
**Date:** 2026-07-25
**PRD ref:** §7, M8 (F01–F05), §3 (exit criteria), §15 (bias/privacy), §17 (voice/video deferred), §18 (Open Question #4)
**Task:** TASK-002 (Phase 2)
**Module scope:** `agents/integrity/` + `services/orchestrator-api/src/modules/integrity/`

---

## Objective

Run fraud and integrity checks after every completed assessment session. Persist one `integrity_flags` row per detected anomaly. Compile flags into `hiring_reports.integrity_summary`. Human reviewer makes all final decisions — the system never auto-rejects.

---

## Architecture

### File layout

```
agents/integrity/
  __init__.py
  checks/
    __init__.py
    ai_generated.py        # F01: statistical heuristics (pure Python)
    duplicate.py           # F02: pgvector ANN vs answer_corpus
    resume_consistency.py  # F03: LLM cross-check vs candidate_profile
    behavioral_anomaly.py  # F04: stub — no voice/video input yet
  agent.py                 # public entry: run_integrity_checks()
  tests/
    __init__.py
    test_ai_generated.py
    test_duplicate.py
    test_resume_consistency.py
    test_agent.py

services/orchestrator-api/src/modules/integrity/
  __init__.py
  service.py    # compile summary; read flags
  router.py     # GET /sessions/{id}/integrity-summary
  schemas.py
```

### Pipeline position

After `_run_behavior_inference` in `agents/evaluation/pipeline.py`:

```
Evaluation → Executive Summary → Behavior Inference → Integrity Checks
```

New helper `_run_integrity_checks(db, session_id)` added to `pipeline.py`. Failure is non-fatal — logs and continues, same pattern as `_generate_executive_summary` and `_run_behavior_inference`.

---

## New DB table: `answer_corpus`

The original 17-table data model has no answer-embedding store. F02 requires one. New Alembic migration (`0002_answer_corpus` or next available revision).

```sql
id                  uuid PK default gen_random_uuid()
org_id              uuid NOT NULL FK→orgs(id)
session_id          uuid NOT NULL FK→assessment_sessions(id)
session_question_id uuid NOT NULL FK→session_questions(id)
answer_embedding    vector(1536) NOT NULL
created_at          timestamptz NOT NULL default now()

UNIQUE(session_question_id)
INDEX hnsw (answer_embedding vector_cosine_ops) WITH (m=16, ef_construction=64)
INDEX btree (org_id)
RLS: org_id = current_setting('app.current_org_id')::uuid
```

**Corpus growth:** all completed sessions ingest after flagging. Ingest is not gated on recruiter review — waiting for review would delay corpus growth indefinitely. Flagged answers are still valid reference data for future similarity checks.

SQLAlchemy model: `services/orchestrator-api/src/models/answer_corpus.py`

---

## F01 — AI-Generated/Scripted Detection

**Implementation:** pure Python, no LLM, no embeddings.

Three statistical signals applied to all `long_text` answered questions in the session:

| Signal | Measurement | Flag threshold |
|---|---|---|
| Structural uniformity | Sentence-count variance and bullet/prose ratio across all long-text answers | Population std-dev of sentence counts < 1.5, AND all answers share same formatting pattern (all bulleted or all prose) |
| Latency anomaly | Characters typed per second: `len(answer_text) / (answered_at - session.started_at).seconds` per answer | Sustained rate > 20 chars/sec for any answer (implausible for live typing) |
| Phrasing divergence | Embed all long-text answers; compute mean cosine similarity between formal answers and the session's shortest answer (proxy for candidate's casual register) | Mean cosine similarity < 0.30 (vocabulary cliff) |

Severity:
- 1 signal triggered → `low`
- 2 signals triggered → `medium`
- All 3 signals triggered → `high`

One `integrity_flags` row per session (flag_type `ai_generated`). `session_question_id` is NULL (session-level flag). Evidence field contains per-signal stats: `"structural_std=0.8, latency_max=24cps, phrasing_sim=0.22"`.

Skip F01 if fewer than 2 long-text answered questions exist (insufficient signal).

---

## F02 — Duplicate/Near-Duplicate Detection

**Implementation:** pgvector ANN + OpenAI embeddings (reuse `embed_texts` from `question_sets/embeddings.py`).

Steps:
1. Embed all `answer_text` values for the session in one batch call.
2. For each answer embedding, ANN query against `answer_corpus` scoped to `org_id`:
   ```sql
   SELECT session_question_id, 1 - (answer_embedding <=> $embedding) AS similarity
   FROM answer_corpus
   WHERE org_id = $org_id
   ORDER BY similarity DESC
   LIMIT 3
   ```
3. Similarity ≥ 0.92 → flag `duplicate_answer`, severity `high`; 0.85–0.91 → severity `medium`. Below 0.85 → no flag.
4. One `integrity_flags` row per flagged answer. `session_question_id` is set. Evidence: `"cosine_similarity=0.94 vs session_question_id=<uuid>"`.
5. After all checks: ingest this session's embeddings into `answer_corpus` (bulk insert, one row per answered question).

---

## F03 — Resume-Answer Consistency

**Implementation:** one LLM pass (claude-sonnet-4-6) with forced tool use.

Input:
- All long-text answers concatenated as `Q{n}: {text}\nA: {answer_text}`
- `candidate_profile.skill_matrix` (JSONB serialized)
- `candidate_profile.experience_matrix` (JSONB serialized)

Tool: `check_resume_consistency`

Tool output schema:
```json
{
  "discrepancies": [
    {
      "claim": "string",
      "present_in_resume": false,
      "conflict_type": "skill_absent | experience_absent | timeline_conflict | minor_embellishment",
      "evidence": "string",
      "answer_sequence_no": 3
    }
  ]
}
```

Severity mapping:
| `conflict_type` | Severity |
|---|---|
| `timeline_conflict` | `high` |
| `skill_absent` | `medium` |
| `experience_absent` | `medium` |
| `minor_embellishment` | `low` |

One `integrity_flags` row per discrepancy. `session_question_id` resolved from `answer_sequence_no` → `session_questions.sequence_no`. Evidence = the LLM's evidence string.

Skip F03 if `candidate_profile_id` is NULL on the session (no resume was parsed).

---

## F04 — Behavioral Signal Anomalies (stub)

The `behavioral_anomaly` flag type exists in the schema. No detection logic is implemented because no voice/video input exists (PRD §17, deferred). `behavioral_anomaly.py` contains only a module-level docstring:

```python
"""
Behavioral signal anomaly detection (M8-F04).
Deferred: requires voice/video session data (PRD §17).
When voice/video modalities ship, implement:
  - long pause detection
  - confidence mismatch between verbal and written responses
  - multi-speaker audio detection
All findings are flags for human review only — never automatic reject.
"""
```

The function `check_behavioral_anomalies(session_id, db) -> list[FlagResult]` is defined and returns `[]` always.

---

## F05 — Integrity Summary

After all checks, compile all `integrity_flags` rows for the session and write `hiring_reports.integrity_summary`:

```json
{
  "flagged_count": 2,
  "overall_risk": "medium",
  "human_review_required": true,
  "flags": [
    {
      "type": "ai_generated",
      "severity": "medium",
      "evidence": "structural_std=0.8, latency_max=24cps, phrasing_sim=0.22",
      "question_id": null
    },
    {
      "type": "duplicate_answer",
      "severity": "high",
      "evidence": "cosine_similarity=0.94 vs session_question_id=<uuid>",
      "question_id": "<uuid>"
    }
  ],
  "open_question": "Labeled validation set not available; recall >85% / FP <10% targets (PRD §3) cannot be verified — see TASK-002 Open Question #4."
}
```

`overall_risk` logic:
- Any `high` flag → `high`
- Two or more `medium` flags → `medium`
- Otherwise → `low`

`human_review_required = true` if `overall_risk` is `high` or `medium`.

`open_question` field is always present in `integrity_summary` until a labeled validation set ships.

---

## Public API

### Agent entry point

```python
# agents/integrity/agent.py

def run_integrity_checks(
    session_id: uuid.UUID,
    db_factory: Callable[[], Session],
) -> None:
    ...
```

- Opens its own DB session via `db_factory()`
- Runs F01 → F02 → F03 → F04 (stub) in sequence
- Writes `integrity_flags` rows for every detected anomaly
- Ingests embeddings into `answer_corpus` (F02)
- Calls `_compile_integrity_summary` to write `hiring_reports.integrity_summary`
- On any exception: logs, returns — pipeline continues

### Internal result type

```python
@dataclass
class FlagResult:
    flag_type: str   # 'ai_generated' | 'duplicate_answer' | 'resume_inconsistency' | 'behavioral_anomaly'
    severity: str    # 'low' | 'medium' | 'high'
    evidence: str
    session_question_id: uuid.UUID | None
```

Each check function returns `list[FlagResult]`. `agent.py` persists them.

### Module router

**`GET /sessions/{session_id}/integrity-summary`**
- Auth: recruiter/admin JWT
- Org-scoped
- Returns compiled `integrity_summary` from `hiring_reports` + full `integrity_flags` list
- 404 if no report exists yet

---

## Pipeline wiring

In `agents/evaluation/pipeline.py`, after `_run_behavior_inference`:

```python
_run_integrity_checks(db, session_id)
```

New helper:
```python
def _run_integrity_checks(db: Session, session_id: uuid.UUID) -> None:
    try:
        from agents.integrity.agent import run_integrity_checks
        run_integrity_checks(session_id=session_id, db_factory=lambda: db)
    except Exception:
        logger.exception("integrity checks failed for session %s", session_id)
```

---

## Tests

| File | Cases |
|---|---|
| `test_ai_generated.py` | uniform answers → flag medium; varied answers → no flag; latency anomaly alone → flag low; <2 long-text Qs → skip |
| `test_duplicate.py` | similarity ≥ 0.92 → flag high; 0.87 → flag medium; 0.80 → no flag; corpus ingest confirmed after checks |
| `test_resume_consistency.py` | timeline conflict → flag high; skill absent → flag medium; all claims present → no flag; NULL candidate_profile_id → skip |
| `test_agent.py` | happy path (flags written + corpus ingested + integrity_summary on report); LLM failure on F03 → non-fatal, F01/F02 flags still written; zero answers → no flags, empty summary |

All tests mock `openai.OpenAI` (embeddings) and `anthropic.Anthropic` (F03 LLM). No live API calls.

---

## Constraints

- §15: No protected characteristics referenced in any check or evidence field
- PRD §7 M8-F04: voice/video anomaly flags are for human review only, never automatic reject — enforced by stub
- PRD §7 M8-F05: integrity summary never triggers automatic reject — `human_review_required` is advisory only
- `integrity_flags` has no UNIQUE constraint — multiple flags per session are valid
- Non-fatal: any check failure logs and continues; a missing integrity summary does not block report generation
- Open Question #4 (§18): labeled validation set required to verify recall >85% / FP <10% — `open_question` field in every summary documents this gap explicitly

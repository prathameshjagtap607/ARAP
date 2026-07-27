# Behavior Inference Engine — Design Spec
**Date:** 2026-07-25
**PRD ref:** §7, M7 (F01–F05)
**Task:** TASK-002 (Phase 2)
**Module scope:** `agents/behavior_analysis` ONLY

---

## Objective

Infer behavioral profile from a candidate's full answer set. No self-report questions. No protected-characteristic signals. Outputs persist to `behavior_profiles` for every completed assessment session.

---

## Architecture

### File layout

```
agents/behavior_analysis/
  __init__.py       (empty, already exists)
  prompts.py        system prompts + tool schemas for both LLM passes
  agent.py          public entry point: infer_behavior()
  tests/
    __init__.py
    test_agent.py
```

### Pipeline position

After `evaluation_pipeline` writes scores and the executive summary, a new helper `_run_behavior_inference` is called at the end of `agents/evaluation/pipeline.py`. Behavior inference runs once all question evaluations are committed. Failure is non-fatal — same pattern as `_generate_executive_summary`.

### Data flow

```
session_questions (answer_text IS NOT NULL)
  → formatted as "Q{n} [{category}]: {text}\nA: {answer_text}"
  → Pass 1 LLM call: extract_behavioral_signals()
      returns: language_patterns, decision_framing, response_structure,
               stress_response, conflict_eq_patterns, cross_answer_themes
  → Pass 2 LLM call: synthesize_behavior_profile()
      input: signals only (no raw Q&A)
      returns: all 9 behavior_profiles columns
  → UPSERT into behavior_profiles (unique on session_id)
```

---

## LLM Passes

### Pass 1 — Behavioral Signal Extraction

**Model:** `claude-sonnet-4-6`
**Tool:** `extract_behavioral_signals`

System prompt instructs the model to read the full Q&A set and identify observable behavioral patterns. Explicit §15 exclusion is stated in the system prompt:

> "Do not infer, mention, score, or reference anything related to age, gender, race, ethnicity, religion, disability, national origin, physical appearance, or any other protected characteristic. Do not treat emotional expression as a hiring criterion."

Tool output schema:
```json
{
  "language_patterns": "string",       // directive vs collaborative phrasing
  "decision_framing": "string",        // data-driven vs intuitive framing
  "response_structure": "string",      // structured/systematic vs free-flowing
  "stress_response": "string",         // from Stress-category questions only
  "conflict_eq_patterns": "string",    // from Conflict Resolution/Teamwork questions
  "cross_answer_themes": "string"      // recurring patterns across the full set
}
```

If no Stress-category questions exist, `stress_response` = `"No stress-category questions in this set."`. Same for `conflict_eq_patterns`.

### Pass 2 — Profile Synthesis

**Model:** `claude-sonnet-4-6`
**Tool:** `synthesize_behavior_profile`

Input is the extracted signals from Pass 1 only — raw Q&A is not re-sent. §15 exclusion repeated in system prompt.

Tool output schema maps to the 9 `behavior_profiles` columns:

| Column | Type | Description |
|---|---|---|
| `disc_style` | JSONB | `{primary, secondary, confidence: 0-1, rationale}` |
| `big_five` | JSONB | `{openness, conscientiousness, extraversion, agreeableness, emotional_stability}` each with `{direction: high/moderate/low, evidence}` |
| `leadership_style` | text | e.g. "Collaborative / servant leader" + one-sentence rationale |
| `decision_style` | text | e.g. "Analytical with iterative validation" + rationale |
| `communication_style` | text | e.g. "Direct and structured; prefers written clarity" |
| `work_style` | text | e.g. "Independent executor; thrives with clear scope" |
| `stress_signal` | text | Observable patterns under pressure; "Insufficient signal" if no stress Qs |
| `eq_signal` | text | Conflict/teamwork emotional intelligence indicators |
| `team_compatibility_signal` | text | **Always prefixed "Recruiter discussion prompt:"** — describes candidate's preferred collaboration style; NEVER a pass/fail verdict (M7-F05) |

`team_compatibility_signal` includes `org_working_style` in the synthesis prompt when provided (from `job_assessment.culture_values`); if `None`, the signal describes the candidate's style without comparison.

---

## Public API

```python
# agents/behavior_analysis/agent.py

def infer_behavior(
    session_id: uuid.UUID,
    db_factory: Callable[[], Session],
    org_working_style: str | None = None,
) -> None:
    ...
```

- Loads all `session_questions` for the session where `answer_text IS NOT NULL`
- Skips (returns without error) if zero answered questions
- Calls Pass 1, then Pass 2
- Upserts into `behavior_profiles`
- On any exception: logs, returns — pipeline continues

---

## Pipeline Wiring

In `agents/evaluation/pipeline.py`, add after `_generate_executive_summary`:

```python
_run_behavior_inference(db, session_id, job)
```

New helper:
```python
def _run_behavior_inference(db, session_id, job):
    try:
        from agents.behavior_analysis.agent import infer_behavior
        org_working_style = ", ".join(job.culture_values) if job and job.culture_values else None
        infer_behavior(session_id=session_id, db_factory=lambda: db, org_working_style=org_working_style)
    except Exception:
        logger.exception("behavior inference failed for session %s", session_id)
```

---

## Tests

File: `agents/behavior_analysis/tests/test_agent.py`

| # | Case | Assertion |
|---|---|---|
| 1 | Happy path — 5 answered Qs across categories | `behavior_profiles` row written; all 9 fields non-null |
| 2 | All `answer_text = None` | Returns without error; no DB write |
| 3 | LLM failure on Pass 1 | Exception caught, logged; no crash; no partial DB write |

All tests mock `anthropic.Anthropic` — no live API calls.

---

## Constraints

- §15: Protected characteristics excluded explicitly from both pass prompts
- M7-F05: `team_compatibility_signal` is a recruiter discussion prompt, never automated pass/fail
- No self-report questions allowed in the answer set (enforced by question generation, not this agent — this agent trusts the set it receives)
- `behavior_profiles` has `UNIQUE (session_id)` — upsert on conflict
- Non-fatal: any failure logs and continues; a missing profile does not block report generation

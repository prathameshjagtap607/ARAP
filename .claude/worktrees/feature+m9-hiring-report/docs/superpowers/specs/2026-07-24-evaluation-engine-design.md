# Evaluation Engine & Basic Report — Design Spec

**Date:** 2026-07-24
**Task:** TASK-001 — M6 (Evaluation Engine) + M9-F01/F02 (Basic Hiring Report)
**PRD refs:** §7 M6, §9 (scoring framework), §3 (turnaround target), §9.5 (verdict bands)
**Status:** Approved for implementation

---

## 1. Scope

### In scope
- M6-F01: Batch scoring of all answers after session submission
- M6-F02: Per-score explanation, evidence quote, strength, improvement area
- M6-F03: Session roll-up — weighted competency scores + 4 composite scores
- M6-F04: Recruiter calibration override captured as labeled training data
- M9-F01: Executive summary + Final Verdict
- M9-F02: Report sections (composite scores, HR questions, training needs, next round)

### Out of scope (Phase 2 / TASK-002)
- Behavior inference (M7), fraud detection (M8)
- Integrity summary in report
- Candidate-facing dashboard score display (M10)

---

## 2. Architecture & Data Flow

Submit triggers a two-phase pipeline via FastAPI `BackgroundTasks`:

```
POST /sessions/{id}/submit
  └─ submit_session()  [sync, fast]
       ├─ marks session.status = "completed"
       ├─ returns SubmitResponse immediately
       └─ BackgroundTask → evaluation_pipeline(session_id, db_factory)
            ├─ Phase 1 — Per-answer scoring (LLM, parallel per question)
            │     for each session_question with answer_text:
            │       evaluation_agent.score_answer() → writes session_questions.evaluation
            ├─ Phase 2 — Roll-up (pure math)
            │     scoring_agent.roll_up(session_id) → competency + composite scores
            └─ Phase 3 — Report generation
                  report_service.create_report() → LLM exec summary + verdict
                  writes hiring_reports row
```

**Target:** Full pipeline < 5 min (PRD §3). In practice ~2–3 min for a 10-question set.

The submit response returns `status=completed` and `report_ready=false`. Recruiter polls `GET /reports/{session_id}` until the report row exists.

---

## 3. Evaluation Agent (M6-F01, F02)

**File:** `agents/evaluation/agent.py`
**Pattern:** Anthropic tool-use forced call (same as question generation agent)
**Model:** `claude-sonnet-4-6`

### Input per question
- `question` (text)
- `category` (from session_question)
- `target_competencies` (list, from session_question — constrains which competencies are scored)
- `answer_text`
- `difficulty` (easy/medium/hard/expert)
- `job_title` (for context)

### Tool schema output (stored in `session_questions.evaluation`)
```json
{
  "competency_scores": [
    {
      "competency": "problem_solving",
      "score": 4,
      "explanation": "Candidate demonstrated structured decomposition...",
      "evidence_quote": "exact verbatim excerpt from candidate answer",
      "strength": "Clear first-principles reasoning under constraint",
      "improvement": "Did not consider edge cases in the time-pressure scenario"
    }
  ]
}
```

### Competency filtering
The tool schema's `competency` field is an enum constrained to the question's own `target_competencies` list. The LLM can only score competencies the question was designed to assess — never all 20.

### Score scale
1–5 integers per PRD §9.2. Prompt defines anchors:
- 1 = No evidence / incorrect
- 2 = Partial / weak
- 3 = Adequate / expected for level
- 4 = Strong / above expected
- 5 = Exceptional / exemplary

Unanswered questions (answer_text is NULL or blank) receive score=1 across all target competencies with explanation "No answer provided."

---

## 4. Scoring Agent — Roll-Up (M6-F03)

**File:** `agents/scoring/agent.py`
**No LLM** — pure arithmetic.

### Difficulty weights (Section 9.3)
| Difficulty | Weight |
|---|---|
| easy | 1.0 |
| medium | 1.5 |
| hard | 2.0 |
| expert | 3.0 |

### Per-competency score formula
```
score_c = Σ(score_i × diff_weight_i) / Σ(diff_weight_i)
          for all questions i that assessed competency c
```

If a competency has no questions, it is excluded from roll-up (not zeroed).

### Job weightage
Read from `job_assessments.competency_weightage` JSONB (already stored).
Weights are applied when computing composite scores.

### 4 Composite scores
| Composite | Constituent competencies |
|---|---|
| Technical | technical, problem_solving, analytical, financial, business_strategy |
| Leadership | leadership, decision_making, innovation, priority_management, negotiation |
| Communication | communication, presentation, conflict_resolution, customer_handling |
| Behavior | ethics, culture_fit, stress, situational_judgment, behavioral |

```
composite_C = Σ(score_c × weight_c) / Σ(weight_c)
              for competencies c in composite C that have at least one scored question
```

Overall score = simple average of the 4 composite scores.

### Output — `hiring_reports.score_rollup` JSONB
```json
{
  "competency_scores": {"problem_solving": 3.8, "communication": 4.1, ...},
  "composite_scores": {
    "Technical": 3.6,
    "Leadership": 4.1,
    "Communication": 3.2,
    "Behavior": 3.9
  },
  "overall": 3.7,
  "question_count": 10,
  "answered_count": 9
}
```

---

## 5. Verdict Bands (PRD §9.5)

Verdict is derived from `overall` score in `score_rollup`.

| Verdict | Overall score |
|---|---|
| `strong_hire` | ≥ 4.25 |
| `hire` | ≥ 3.50 |
| `consider` | ≥ 2.75 |
| `borderline` | ≥ 2.00 |
| `reject` | < 2.00 |

Verdict is stored in `hiring_reports.verdict` (CHECK constraint already covers the 5 values).

---

## 6. Calibration (M6-F04)

**Endpoint:** `PATCH /sessions/{session_id}/questions/{question_id}/calibration`
**Auth:** recruiter scope (require_user)

### Request body
```json
{
  "override_score": 3,
  "comment": "Candidate expanded on this in phone screen"
}
```

### Behaviour
1. Merges `calibration` key into `session_questions.evaluation` JSONB:
```json
{
  "competency_scores": [...],
  "calibration": {
    "override_score": 3,
    "comment": "...",
    "overridden_by": "user_uuid",
    "overridden_at": "2026-07-24T10:30:00Z"
  }
}
```
2. Appends an entry to `hiring_reports.reviewer_override` JSONB (list of all overrides for this session) for labeled training data capture per M6-F04.

Calibration does **not** re-trigger roll-up or change the stored verdict. This is intentional — overrides are training data, not live score adjustments, in Phase 1.

---

## 7. Basic Hiring Report (M9-F01, F02)

**Module:** `services/orchestrator-api/src/modules/reports/`

### Executive summary generation
One LLM call (claude-sonnet-4-6) after roll-up is complete.

Input: candidate name, job title, composite scores, verdict, overall score.
Output: 2–3 sentence plain-English summary stored in `hiring_reports.executive_summary`.

Also populates (via structured LLM output):
- `suggested_hr_questions` (3 follow-up questions based on weak competencies)
- `recommended_next_round` (e.g., "Technical Panel Interview")
- `training_needs` (top 2 gaps to address)

### GET endpoint
```
GET /reports/{session_id}
```
Auth: require_user (recruiter/panel only — raw scores never exposed to candidate)

Response schema:
```json
{
  "session_id": "uuid",
  "verdict": "hire",
  "executive_summary": "...",
  "composite_scores": {"Technical": 3.6, ...},
  "overall_score": 3.7,
  "suggested_hr_questions": ["...", "...", "..."],
  "recommended_next_round": "Technical Panel Interview",
  "training_needs": ["...", "..."],
  "report_ready": true,
  "created_at": "2026-07-24T..."
}
```

If the report row doesn't exist yet, returns `report_ready: false` with nulls — no 404.

---

## 8. Competency Rubric (Section 9.1)

**File:** `agents/scoring/rubric.py`

Maps each of the 20 competencies to their composite category and a 1-line description used in LLM prompts. Derived from `CATEGORY_TO_COMPETENCY` already in `question_generation/prompts.py`.

---

## 9. Files

| Action | File |
|---|---|
| Create | `agents/evaluation/agent.py` |
| Create | `agents/evaluation/prompts.py` |
| Create | `agents/scoring/agent.py` |
| Create | `agents/scoring/rubric.py` |
| Create | `services/orchestrator-api/src/modules/reports/__init__.py` |
| Create | `services/orchestrator-api/src/modules/reports/service.py` |
| Create | `services/orchestrator-api/src/modules/reports/router.py` |
| Create | `services/orchestrator-api/src/modules/reports/schemas.py` |
| Modify | `services/orchestrator-api/src/modules/sessions/service.py` |
| Modify | `services/orchestrator-api/src/modules/sessions/router.py` |
| Modify | `services/orchestrator-api/src/main.py` |

**No Alembic migration** — all required columns already exist.

---

## 10. Error Handling

- If the evaluation LLM call fails for a question, log the error and store `{"error": "evaluation_failed"}` in that question's `evaluation` column. Roll-up skips errored questions.
- If roll-up produces no scored questions at all, `verdict = "reject"` and summary notes insufficient data.
- If the report LLM call fails, `executive_summary` is set to a fallback template string derived from the structured data — report still gets written so `report_ready` becomes true.

---

## 11. Testing

- Unit test `scoring_agent.roll_up()` with fixture data — pure math, fully deterministic.
- Unit test verdict band mapping.
- Integration test: seed a completed session with 3 answered questions, call `evaluation_pipeline()`, assert `hiring_reports` row exists with correct verdict tier.
- Calibration endpoint test: override a score, assert JSONB merge is correct.

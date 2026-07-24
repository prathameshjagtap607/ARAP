# M4 — Question Generation Engine: Design Spec

**Date:** 2026-07-24
**PRD ref:** §6 M4-F01–F06, §7 Prompt Template Pattern, §8 Question Generation & Test Flow
**Task:** TASK-001 / question-gen session
**Status:** Approved — proceed to implementation plan

---

## 1. Scope

Implements M4 in full:

- **M4-F01** Upfront batch generation (one LLM call, complete set before test is sent)
- **M4-F02** Category coverage weighted by `competency_weightage` from `job_profile`
- **M4-F03** At least one resume-referenced question per set
- **M4-F04** Risk-flag targeted questions seeded from M3 `risk_flags[]`
- **M4-F05** No-repeat guarantee via pgvector cosine similarity vs `question_fingerprints`
- **M4-F06** Set finalization and lock — immutable once sent

Out of scope: test delivery (M5), evaluation (M6), email sending.

---

## 2. Module boundaries

### `agents/question_generation/` (repo root — no DB access)

| File | Purpose |
|------|---------|
| `prompts.py` | Builds system prompt + user message from structured inputs |
| `agent.py` | `run_question_generation_agent(...)` → `list[dict] \| None` |

Pattern: identical to `agents/candidate_profile/` — `anthropic.Anthropic()`, forced `tool_choice={"type":"tool","name":"generate_question_set"}`, return None on any exception (non-fatal).

Model: `claude-sonnet-4-6`

### `services/orchestrator-api/src/modules/question_sets/`

| File | Purpose |
|------|---------|
| `schemas.py` | Pydantic request/response models |
| `service.py` | Orchestration: load data → call agent → embed → dedup → persist → lock |
| `router.py` | Two endpoints: POST generate, GET by session |

---

## 3. Agent contract

### Tool definition: `generate_question_set`

Input schema (what the LLM must populate):

```json
{
  "questions": [
    {
      "question": "string",
      "category": "string (one of 21 PRD categories)",
      "target_competencies": ["string"],
      "difficulty": "easy|medium|hard|expert",
      "answer_format": "multiple_choice|short_text|long_text",
      "options": ["string"],
      "resume_reference": true
    }
  ]
}
```

- `options` present only when `answer_format == "multiple_choice"`
- `resume_reference` is `true` on questions that directly cite the candidate's resume; `false` otherwise
- The LLM is instructed to produce `target + ceil(target × 0.25)` questions (buffer for dedup)

### Prompt inputs

| Variable | Source |
|----------|--------|
| `job_profile_json` | `job_assessments.job_profile` |
| `candidate_profile_json` | `candidate_profiles` — `summary`, `skill_matrix["aligned"]`, `strengths`, `experience_matrix` |
| `category_weightage_json` | Derived in service: 21-category → question-count map (computed from `competency_weightage`, total = target_count) |
| `difficulty_level` | `job_profile["difficulty_level"]` |
| `risk_flags_json` | `candidate_profiles.risk_flags[]` |
| `target_question_count` | `target + buffer` (passed to agent) |

### System prompt (exact per PRD §7)

```
You are the Question Generation Agent for a personalized recruitment
assessment. Generate the COMPLETE question set for this candidate in one
pass. Never repeat or closely paraphrase any question already generated
for this org's question-fingerprint history. Match the category weightage
and difficulty level supplied.
```

---

## 4. Service orchestration (`service.py`)

```
generate_question_set(session_id, org_id, db) -> QuestionSetResponse:

1. Load assessment_session (404 if not found, org_id must match)
2. Check: question_set already exists for session_id → 409
3. Load job_assessment → job_profile (422 if NULL)
4. Load candidate_profile via session.candidate_profile_id (422 if missing)
5. Derive category_weightage_json:
     - competency_weightage from job_profile (dict competency→weight, sum=100)
     - Map each of 21 PRD categories to the closest competency
     - Distribute target_count questions proportionally (round to int, fix rounding remainder on largest bucket)
6. Call run_question_generation_agent(..., target_count=target + ceil(target × 0.25))
     → None → raise HTTPException(502)
7. Embed all returned questions (OpenAI text-embedding-3-small, batch call)
8. For each question embedding, query question_fingerprints WHERE org_id = org_id
     ORDER BY question_embedding <=> embedding LIMIT 1
     → if max_similarity >= 0.92: mark rejected
9. accepted = [q for q not rejected]
10. If len(accepted) < target:
      - Second LLM call for (target - len(accepted)) questions, same prompt
      - Embed + dedup the gap questions
      - Append accepted gap questions
11. If still < target: raise HTTPException(502, "Partial set — not locking")
12. Truncate accepted to exactly target (sorted by sequence)
13. Validate: at least one question has resume_reference=True
      → if not: single-question regeneration pass requesting a resume-referenced question
14. BEGIN TRANSACTION:
      INSERT question_set (org_id, session_id, generation_prompt_version, locked_at=NULL)
      INSERT session_questions (sequence_no 1..N, all fields from PRD contract)
      INSERT question_fingerprints (org_id, question_text, question_embedding, question_set_id)
      UPDATE question_set SET locked_at = now()
    COMMIT
15. Return QuestionSetResponse
```

### No-repeat guarantee detail

- Threshold: **cosine similarity ≥ 0.92** → reject
- Buffer: `ceil(target × 0.25)` extra questions in first pass
- Max LLM calls: **2** (first pass + one gap-fill pass)
- Fingerprints inserted **inside the same transaction as the lock** — crash before commit leaves no orphan fingerprints and no locked set (safe to retry)
- Fingerprints are **org-scoped** — a question used for Candidate A at Org X does not block Org Y

---

## 5. API endpoints

### `POST /question-sets/generate/{session_id}`

Auth: `require_user` (user or admin); `org_id` from JWT claims only.

- **201** `QuestionSetResponse` — set generated and locked
- **404** session not found
- **409** set already locked for this session
- **422** `candidate_profile` missing or `job_profile` NULL
- **502** LLM failure or partial set after 2 passes

### `GET /question-sets/{session_id}`

Auth: `require_user` OR `RequireCandidateScope` (candidate who owns the session).

- **200** `QuestionSetResponse`
- **404** set not yet generated for this session

### Response schema (`QuestionSetResponse`)

```python
class QuestionSetResponse(BaseModel):
    id: UUID
    session_id: UUID
    generated_at: datetime
    locked_at: datetime
    generation_prompt_version: str
    questions: list[QuestionItem]

class QuestionItem(BaseModel):
    id: UUID
    sequence_no: int
    question: str
    category: str
    target_competencies: list[str]
    difficulty: str
    answer_format: str
    options: list[str] | None
```

---

## 6. Category → competency mapping

The 21 PRD categories map to competency names. Mapping lives in `prompts.py` as a constant dict. When `competency_weightage` from `job_profile` uses names that don't match exactly, the service does a case-insensitive prefix match then falls back to distributing evenly across unmapped categories.

---

## 7. Tests

### `agents/question_generation/tests/test_agent.py`
- Mocked Anthropic client returning valid tool_use block
- Validates: all required fields present, at least one `resume_reference: true`, category values within 21 allowed, difficulty values valid
- Validates: exception from Anthropic → agent returns None

### `tests/modules/question_sets/test_service.py`
- Dedup: pre-insert fingerprint at similarity 0.95 → question rejected; at 0.88 → accepted
- Resume-reference enforcement: set with no `resume_reference: true` → triggers gap pass
- Partial set after 2 passes → 502, no question_set row committed

### `tests/modules/question_sets/test_router.py`
- 404: session not found
- 422: no candidate_profile; job_profile NULL
- 409: generate called twice on same session
- 201: happy path — response has correct structure, locked_at not null
- GET before generate → 404
- GET after generate → 200 with questions

---

## 8. Performance target

p95 < 6s per question (PRD §3). For a 10-question set:
- First LLM call (12–13 questions): ~3–4s
- Embed 12–13 questions (batch): ~0.3s
- pgvector similarity queries (12–13 × single-row query): ~0.2s
- Second pass (if needed, 0–3 questions): ~1–2s
- DB writes: ~0.1s
- **Total: ~4–6s** for 10-question set → well within 6s per question target

---

## 9. Architectural decisions

- `question_fingerprints` inserted **inside** the lock transaction — no orphans possible on failure
- `generation_prompt_version` is a string constant in `prompts.py` (e.g., `"v1.0"`) — increment manually when prompt changes; enables future A/B analysis via M11-F03
- `resume_reference` field is **in the tool schema** (LLM must populate it) — not inferred post-hoc
- Category-to-count distribution happens in `service.py`, not in the prompt — the agent receives exact per-category counts, making the output deterministic and testable without mocking the LLM
- Two-pass max keeps worst-case latency predictable; partial set is an error (not silently accepted)
- `question` JSONB column stores the full PRD question object; `category`, `target_competencies`, `difficulty`, `answer_format`, `options` are also top-level columns (schema already set this way) — service writes both

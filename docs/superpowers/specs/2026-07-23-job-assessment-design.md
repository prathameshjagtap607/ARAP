# Job Assessment Builder & Job Description Agent — Design

**Date:** 2026-07-23
**PRD ref:** §7 (Job Description Agent), M1-F01 – M1-F04
**Task:** TASK-001
**Phase:** 1 — MVP
**Status:** Approved

---

## Scope

Build M1 (Job Assessment Builder) and the Job Description Agent (§7) end-to-end.
Module boundaries: `services/orchestrator-api/src/modules/job_assessments`,
`services/orchestrator-api/src/modules/competency_library`,
`agents/job_description`.

Out of scope for this session: resume ingestion, question generation, test delivery,
all M2–M9 concerns.

---

## Cross-Cutting Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Weightage validation | Service layer, ±0.01 float tolerance | Enforced before any DB write; HTTP 422 on failure |
| JD agent execution | Synchronous in service layer | No queue needed at MVP scale; p95 target is < 2 s for this normalization step |
| JD agent model | `claude-haiku-4-5-20251001` | Normalization task — Haiku is sufficient per model tier rules |
| JD agent output format | Claude tool_use structured output | Guaranteed JSON schema; avoids fragile string parsing |
| Template storage | Flag columns on `job_assessments` | No separate table; templates are assessments with `is_template=true` |
| `job_profile` storage | `jsonb` column on `job_assessments` | Co-located with source; single row read satisfies downstream agents |
| Competency ↔ assessment link | Text array on assessment (`behavioral_competencies`, `leadership_competencies`) | No FK to library; custom one-off competencies remain allowed per PRD |
| Candidate upsert on invite | `INSERT … ON CONFLICT (org_id, email) DO NOTHING RETURNING id` | Prevents duplicate candidates per org |
| Auth | `require_user` on all M1 endpoints | Admin and user roles both create/manage assessments |

---

## Migration: `0002_job_assessment_templates_profile`

Three columns added to existing `job_assessments` table:

| Column | Type | Constraint | Default |
|---|---|---|---|
| `is_template` | `boolean` | `NOT NULL` | `false` |
| `role_family` | `text` | nullable | — |
| `job_profile` | `jsonb` | nullable | — |

`job_profile` is `NULL` until the JD agent completes. Downstream agents must
tolerate `NULL` and re-trigger generation if needed (out of scope here).

---

## Module: `src/modules/job_assessments/`

### Schemas (`schemas.py`)

**`JobAssessmentCreate`** — all PRD M1-F01 fields:
- `title: str` (required)
- `department: str | None`
- `experience_min: int | None`, `experience_max: int | None`
- `required_skills: list[str]` (default `[]`)
- `preferred_skills: list[str]` (default `[]`)
- `responsibilities: str | None`
- `education: str | None`
- `certifications: list[str]` (default `[]`)
- `behavioral_competencies: list[str]` (default `[]`)
- `leadership_competencies: list[str]` (default `[]`)
- `culture_values: list[str]` (default `[]`)
- `difficulty_level: Literal["junior","mid","senior","executive"]`
- `duration_minutes: int` (required, `> 0`)
- `competency_weightage: dict[str, float]` (required; validated to sum 100)
- `is_template: bool` (default `False`)
- `role_family: str | None`

**`JobAssessmentUpdate`** — all fields optional (partial PATCH).
`competency_weightage` re-validated if present.

**`CloneRequest`** — optional overrides only:
- `competency_weightage: dict[str, float] | None`
- `required_skills: list[str] | None`
- `preferred_skills: list[str] | None`
- `role_family: str | None`

**`InviteRequest`**:
- `candidate_name: str`
- `candidate_email: EmailStr`
- `time_budget_seconds: int` (`> 0`)

**`InviteResponse`**:
- `assessment_session_id: UUID`
- `candidate_id: UUID`
- `status: str`

**`JobAssessmentResponse`** — all DB columns including `job_profile`, `is_template`, `role_family`, `created_at`.

### Service (`service.py`)

**`validate_weightage(weights: dict[str, float]) -> None`**
Raises `ValueError("competency_weightage must sum to 100")` if
`abs(sum(weights.values()) - 100) > 0.01`.

**`create_assessment(db, org_id, user_id, data: JobAssessmentCreate) -> JobAssessment`**
1. `validate_weightage`
2. Insert row
3. Call `run_job_description_agent(db, assessment)` → writes `job_profile` back
4. Return refreshed row

**`update_assessment(db, org_id, id, data: JobAssessmentUpdate) -> JobAssessment`**
1. Fetch; 404 if not found or wrong org
2. If `competency_weightage` in payload: `validate_weightage`
3. Apply patch fields
4. Re-run JD agent (any field change may affect job_profile)
5. Return

**`clone_assessment(db, org_id, user_id, id, overrides: CloneRequest) -> JobAssessment`**
1. Fetch source; 404 check
2. Copy all fields; apply overrides; set `is_template=False`
3. Re-run JD agent on clone
4. Return new row

**`invite_candidate(db, org_id, assessment_id, user_id, data: InviteRequest) -> InviteResponse`**
1. Fetch assessment; 404 check
2. Upsert `candidates` on `(org_id, email)` — insert or return existing
3. Insert `assessment_sessions` with `status='invited'`, `time_budget_seconds`
4. Return `InviteResponse`

### Router (`router.py`)

```
POST   /job-assessments                  → create_assessment
GET    /job-assessments                  → list (org_id filter; ?is_template=bool)
GET    /job-assessments/{id}             → get one
PATCH  /job-assessments/{id}             → update_assessment
DELETE /job-assessments/{id}             → delete (hard; returns 409 if any assessment_session exists for this assessment)
POST   /job-assessments/{id}/clone       → clone_assessment
POST   /job-assessments/{id}/invite      → invite_candidate
```

All routes: `Depends(require_user)`. `org_id` taken from `claims.org_id`.

---

## Module: `src/modules/competency_library/`

### API

| Method | Path | Notes |
|---|---|---|
| `GET` | `/competency-library` | List org's competencies |
| `POST` | `/competency-library` | Create; unique on `(org_id, name)` → 409 on duplicate |
| `PATCH` | `/competency-library/{id}` | Update `name`, `description`, `rubric_notes` |
| `DELETE` | `/competency-library/{id}` | Hard delete |

All routes: `Depends(require_user)`.

### Schemas

**`CompetencyCreate`**: `name: str`, `description: str | None`, `rubric_notes: str | None`
**`CompetencyUpdate`**: all fields optional
**`CompetencyResponse`**: all DB columns

---

## Agent: `agents/job_description/`

### `agent.py`

**Entry point:** `run_job_description_agent(db: Session, assessment: JobAssessment) -> None`

1. Build prompt from assessment fields (title, skills, responsibilities, competencies, etc.)
2. Call Claude via `anthropic.Anthropic().messages.create(...)` with a `tools` definition
   that enforces the `job_profile` JSON schema
3. Extract tool_use result block
4. Write parsed JSON to `assessment.job_profile`
5. `db.commit()`
6. On any exception: log error, leave `job_profile=None` (non-fatal — assessment is still created)

### `prompts.py`

Contains the tool definition (`job_profile_tool`) and system prompt string.
No business logic — pure strings.

### `job_profile` JSON shape

```json
{
  "normalized_title": "string",
  "role_summary": "string",
  "key_responsibilities": ["string"],
  "required_skills": ["string"],
  "preferred_skills": ["string"],
  "education_requirements": "string",
  "certifications": ["string"],
  "competency_weightage_map": { "competency_name": 0.0 },
  "difficulty_level": "junior|mid|senior|executive",
  "generated_at": "ISO-8601 datetime"
}
```

`competency_weightage_map` mirrors `assessment.competency_weightage` — agent may
rename/normalize keys but values must sum to 100.

---

## Config Changes

`src/config.py` — add:
```python
ANTHROPIC_API_KEY: str
```

`.env.example` — add `ANTHROPIC_API_KEY=` line.

---

## `src/main.py` Changes

Add two `include_router` calls:
```python
from src.modules.job_assessments.router import router as job_assessments_router
from src.modules.competency_library.router import router as competency_library_router

app.include_router(job_assessments_router)
app.include_router(competency_library_router)
```

---

## Tests

```
services/orchestrator-api/tests/
  job_assessments/
    __init__.py
    conftest.py          — org, user, db, auth client fixtures
    test_crud.py         — create/read/update/delete happy paths
    test_weightage.py    — sum=100 passes; sum≠100 → 422; edge: float precision
    test_templates.py    — is_template list filter; clone copies fields; overrides apply
    test_invite.py       — session created; upsert: second invite reuses candidate; 404 on bad assessment
  competency_library/
    __init__.py
    test_crud.py         — CRUD + duplicate name → 409
  job_description/
    __init__.py
    test_agent.py        — mock anthropic client; assert job_profile shape written; assert non-fatal on API error
```

---

## Exit Criteria (M1)

- [ ] `POST /job-assessments` with `competency_weightage` summing to 100 returns 201 with `job_profile` populated
- [ ] `POST /job-assessments` with weightage ≠ 100 returns 422
- [ ] `GET /job-assessments?is_template=true` returns only template assessments
- [ ] `POST /job-assessments/{id}/clone` produces a new non-template row with overrides applied
- [ ] `POST /job-assessments/{id}/invite` creates `assessment_session` with `status='invited'`; second call with same email reuses candidate row
- [ ] `GET /competency-library` returns org-scoped list; duplicate name returns 409
- [ ] All tests pass (`pytest`)

# Candidate Profile Engine — Design

**Date:** 2026-07-24
**PRD ref:** §7, M3-F01 – M3-F04
**Task:** TASK-001
**Phase:** 1 — MVP
**Status:** Approved

---

## Scope

Build M3 (Candidate Profile Engine) end-to-end.
Module boundaries: `services/orchestrator-api/src/modules/candidate_profiles/` and `agents/candidate_profile/` ONLY.
No new migration needed — all target columns exist on `candidate_profiles`.

Out of scope: M4 question generation, test delivery, anything downstream.

---

## Cross-Cutting Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Agent model | `claude-sonnet-4-6` forced tool_use | Consistent with resume_analysis agent; narrative + structured output requires Sonnet |
| Trigger | Separate `POST /candidate-profiles/synthesize` in orchestrator-api | M3 enriches M2 extraction — M2 must run first; clean boundary |
| 404 on missing profile | Yes — 404 if no candidate_profile row | Caller must sequence M2 then M3 |
| 422 on NULL parsing_confidence | Yes — if M2 agent failed, M3 cannot synthesize | M2 design doc: "M3 checks for NULL" |
| skill_matrix shape | Replace with `{"aligned": [...], "raw": <existing>}` | Keeps M2 raw list for M4; M3 aligned list is primary for display |
| experience_matrix | Add `leadership_scope` key, keep existing keys | Additive only — no data loss |
| leadership_level_estimate | Override from agent output | Agent has full context (JD + resume); more accurate than M2 heuristic |
| Auth | `require_user` (org-scoped from JWT) | Consistent with job_assessments module |
| Agent failure | Non-fatal: log + raise HTTPException(502) | Caller retries; partial writes avoided |

---

## New Files

```
agents/candidate_profile/
  __init__.py
  agent.py        # run_candidate_profile_agent(extraction, job_profile) -> dict | None
  prompts.py      # SYSTEM_PROMPT + CANDIDATE_PROFILE_TOOL schema
  tests/
    __init__.py
    test_agent.py

services/orchestrator-api/src/modules/candidate_profiles/
  __init__.py
  router.py       # POST /candidate-profiles/synthesize
                  # GET  /candidate-profiles/{candidate_id}/{job_assessment_id}
  schemas.py      # SynthesizeRequest, CandidateProfileResponse
  service.py      # synthesize_profile(), get_profile()
  tests/
    __init__.py
    test_service.py
    test_router.py
```

No migration. `candidate_profiles` already has: `summary`, `skill_matrix jsonb`,
`experience_matrix jsonb`, `leadership_level_estimate`, `strengths text[]`, `risk_flags text[]`.

---

## Agent: `agents/candidate_profile/`

**Model:** `claude-sonnet-4-6`, `max_tokens=4096`, forced `tool_choice`.

### Input message built from DB

```
RESUME EXTRACTION:
  skills.explicit: [...]
  skills.inferred: [...]
  tech_used: [...]
  employment_history: [...]
  career_timeline: {total_years, job_count, gaps: [...]}
  leadership_indicators: {max_team_size, scope, budget_ownership}
  achievements: [...]
  field_confidence: {...}

JOB PROFILE:
  normalized_title: ...
  role_summary: ...
  key_responsibilities: [...]
  required_skills: [...]
  preferred_skills: [...]
  difficulty_level: ...
```

### Tool schema: `synthesize_candidate_profile`

```json
{
  "summary": "string — 2-3 paragraph narrative: current role, trajectory, standout achievements, domain fit",
  "skill_matrix_aligned": [
    {
      "skill": "string",
      "source": "required | preferred",
      "alignment": "yes | partial | no",
      "estimated_years": "number | null",
      "confidence": "number 0–1",
      "evidence": "string | null — short phrase from resume"
    }
  ],
  "leadership": {
    "level": "IC | Team Lead | Manager | Director | VP-equiv",
    "career_velocity": "string — e.g. 'Promoted 3 times in 5 years'",
    "scope": {
      "team_size": "integer | null",
      "budget": "string | null",
      "geography": "string | null"
    }
  },
  "strengths": ["string — 3–5 concise statements"],
  "risk_flags": ["string — 1–5 complete sentences, each a specific flag"]
}
```

**Risk flag examples** (seeds M4 targeted questions):
- "No direct people-management experience despite Manager title at Acme Corp"
- "7-month gap (Mar–Oct 2023) unexplained in resume"
- "React listed as required; only inferred from a single project description"

---

## Endpoints

### `POST /candidate-profiles/synthesize`

```
Auth:    require_user
Body:    { candidate_id: UUID, job_assessment_id: UUID, org_id: UUID }

Guards:
  - 404 if CandidateProfile row does not exist (M2 not run yet)
  - 422 if profile.parsing_confidence IS NULL (M2 agent failed)
  - 404 if JobAssessment.job_profile IS NULL (JD agent failed — retry M1)

Flow:
  1. Load CandidateProfile row (for extraction fields)
  2. Load JobAssessment row (for job_profile)
  3. Build extraction dict from profile columns
  4. Call run_candidate_profile_agent(extraction, job_profile)
  5. On None return → HTTPException(502, "Profile agent failed — retry")
  6. UPDATE candidate_profiles SET
       summary = agent.summary,
       skill_matrix = {"aligned": agent.skill_matrix_aligned, "raw": existing_raw},
       experience_matrix = {**existing, "leadership_scope": agent.leadership.scope},
       leadership_level_estimate = agent.leadership.level,
       strengths = agent.strengths,
       risk_flags = agent.risk_flags
     WHERE candidate_id = X AND job_assessment_id = Y
  7. db.commit()
  8. Return CandidateProfileResponse

Returns: 200 CandidateProfileResponse (all fields)
```

### `GET /candidate-profiles/{candidate_id}/{job_assessment_id}`

```
Auth:    require_user
Returns: 200 CandidateProfileResponse
         404 if not found
```

---

## Pydantic Schemas (`schemas.py`)

```python
class SynthesizeRequest(BaseModel):
    candidate_id: UUID
    job_assessment_id: UUID
    org_id: UUID

class SkillAligned(BaseModel):
    skill: str
    source: Literal["required", "preferred"]
    alignment: Literal["yes", "partial", "no"]
    estimated_years: Optional[float]
    confidence: float
    evidence: Optional[str]

class LeadershipScope(BaseModel):
    team_size: Optional[int]
    budget: Optional[str]
    geography: Optional[str]

class LeadershipEstimate(BaseModel):
    level: str
    career_velocity: str
    scope: LeadershipScope

class CandidateProfileResponse(BaseModel):
    id: UUID
    candidate_id: UUID
    job_assessment_id: UUID
    org_id: UUID
    summary: Optional[str]
    skill_matrix: dict
    experience_matrix: dict
    leadership_level_estimate: Optional[str]
    strengths: list[str]
    risk_flags: list[str]
    parsing_confidence: Optional[float]
    match_score: Optional[float]

    model_config = ConfigDict(from_attributes=True)
```

---

## Tests

### `agents/candidate_profile/tests/test_agent.py`
- Mock `anthropic.Anthropic().messages.create` → return fake tool_use block
- Assert agent returns parsed dict with all required keys
- Assert agent returns `None` on exception (non-fatal)

### `modules/candidate_profiles/tests/test_service.py`
- Mock `run_candidate_profile_agent` → fixture dict
- Assert DB row updated with correct values
- Assert `skill_matrix["aligned"]` set, `skill_matrix["raw"]` preserved
- Assert `risk_flags` list written

### `modules/candidate_profiles/tests/test_router.py`
- Integration test with `TestClient` + test DB (same pattern as job_assessments)
- `POST /synthesize` → 200 with full profile
- `POST /synthesize` with no existing profile → 404
- `POST /synthesize` with NULL parsing_confidence → 422
- `GET /{candidate_id}/{job_assessment_id}` → 200 after synthesize

---

## Registration

Add to `services/orchestrator-api/src/main.py`:
```python
from src.modules.candidate_profiles.router import router as candidate_profiles_router
app.include_router(candidate_profiles_router, prefix="/candidate-profiles")
```

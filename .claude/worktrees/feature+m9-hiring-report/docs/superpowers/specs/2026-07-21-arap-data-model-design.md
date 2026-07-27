# ARAP Data Model Design

**Date:** 2026-07-21
**PRD ref:** §12 (Data Model), §4 (Users & Roles), §15 (Security)
**Phase:** 0 — Foundation
**Status:** Approved

---

## Scope

All 17 tables required by PRD §12, implemented in PostgreSQL + pgvector.
Target module: `services/orchestrator-api/src/models/` + `migrations/`.

---

## Cross-Cutting Decisions

| Decision | Choice | Rationale |
|---|---|---|
| PK type | `UUID` via `gen_random_uuid()` | No enumerable IDs exposed to clients |
| Array columns | PostgreSQL native `text[]` | Queryable without join tables at MVP scale |
| RLS | `ENABLE ROW LEVEL SECURITY` + policy `USING (org_id = current_setting('app.current_org_id')::uuid)` on every tenant-scoped table | Enforced at DB layer, not only ORM |
| pgvector index | `hnsw` (m=16, ef_construction=64) on `question_embedding` | Better recall than ivfflat; no nlist to tune |
| Vector dimension | `vector(1536)` | Matches text-embedding-3-small; change before first migration if provider differs |
| `prompt_templates` org scoping | `org_id` nullable — NULL = global/platform default | Allows platform-wide defaults overridable per tenant (PRD §M12-F02) |
| `audit_logs` | App DB role has INSERT only — no UPDATE/DELETE granted | Append-only enforced via GRANT, not triggers |
| Enums | Implemented as PostgreSQL `CHECK` constraints (not PG ENUM types) | Easier to ALTER without migration gymnastics |

---

## Tables

### `orgs`
Root tenant table. No `org_id` FK. No RLS.

```sql
id          uuid PK default gen_random_uuid()
name        text NOT NULL
plan_tier   text NOT NULL default 'trial'
created_at  timestamptz NOT NULL default now()
```

---

### `users`
Admin/User workspace identities. Password-based login only.

```sql
id             uuid PK default gen_random_uuid()
org_id         uuid NOT NULL FK→orgs(id)
email          text NOT NULL
role           text NOT NULL  CHECK(role IN ('user','admin'))
password_hash  text NOT NULL
created_at     timestamptz NOT NULL default now()

UNIQUE(org_id, email)
```
RLS: `org_id = current_org_id`

---

### `job_assessments`
One record per open requisition. Grounds all downstream agents.

```sql
id                      uuid PK default gen_random_uuid()
org_id                  uuid NOT NULL FK→orgs(id)
title                   text NOT NULL
department              text
experience_min          int
experience_max          int
required_skills         text[] NOT NULL default '{}'
preferred_skills        text[] NOT NULL default '{}'
responsibilities        text
education               text
certifications          text[] NOT NULL default '{}'
behavioral_competencies text[] NOT NULL default '{}'
leadership_competencies text[] NOT NULL default '{}'
culture_values          text[] NOT NULL default '{}'
difficulty_level        text NOT NULL CHECK(difficulty_level IN ('junior','mid','senior','executive'))
duration_minutes        int NOT NULL
competency_weightage    jsonb NOT NULL
created_by              uuid NOT NULL FK→users(id)
created_at              timestamptz NOT NULL default now()
```
RLS: `org_id`

---

### `candidates`
Lightweight authenticated identity, scoped to one `assessment_session`.

```sql
id                      uuid PK default gen_random_uuid()
org_id                  uuid NOT NULL FK→orgs(id)
name                    text NOT NULL
email                   text NOT NULL
resume_file_url         text
linkedin_url            text
github_url              text
portfolio_url           text
auth_method             text CHECK(auth_method IN ('magic_link','otp','password'))
password_hash           text
login_token_hash        text
login_token_expires_at  timestamptz
last_login_at           timestamptz
created_at              timestamptz NOT NULL default now()

UNIQUE(org_id, email)
```
RLS: `org_id`

---

### `clients`
Lightweight authenticated identity, scoped to explicitly shared reports only.

```sql
id                      uuid PK default gen_random_uuid()
org_id                  uuid NOT NULL FK→orgs(id)
name                    text NOT NULL
email                   text NOT NULL
auth_method             text CHECK(auth_method IN ('magic_link','otp','password'))
password_hash           text
login_token_hash        text
login_token_expires_at  timestamptz
last_login_at           timestamptz
created_at              timestamptz NOT NULL default now()

UNIQUE(org_id, email)
```
RLS: `org_id`

---

### `report_shares`
Junction table scoping Client access to specific reports. Client JWTs carry `report_share_id` claim.

```sql
id                uuid PK default gen_random_uuid()
org_id            uuid NOT NULL FK→orgs(id)
hiring_report_id  uuid NOT NULL FK→hiring_reports(id)
client_id         uuid NOT NULL FK→clients(id)
shared_by         uuid NOT NULL FK→users(id)
expires_at        timestamptz
revoked_at        timestamptz
created_at        timestamptz NOT NULL default now()
```
RLS: `org_id`. API enforces `revoked_at IS NULL AND (expires_at IS NULL OR expires_at > now())`.

---

### `candidate_profiles`
M3 output: structured synthesis of parsed resume against a specific job assessment.

```sql
id                        uuid PK default gen_random_uuid()
org_id                    uuid NOT NULL FK→orgs(id)
candidate_id              uuid NOT NULL FK→candidates(id)
job_assessment_id         uuid NOT NULL FK→job_assessments(id)
summary                   text
skill_matrix              jsonb NOT NULL default '{}'
experience_matrix         jsonb NOT NULL default '{}'
leadership_level_estimate text
strengths                 text[] NOT NULL default '{}'
risk_flags                text[] NOT NULL default '{}'
parsing_confidence        numeric(4,3) CHECK(parsing_confidence BETWEEN 0 AND 1)
created_at                timestamptz NOT NULL default now()
```
RLS: `org_id`

---

### `assessment_sessions`
One per candidate per job assessment. Candidate JWTs carry `assessment_session_id` claim restricting them to this single row.

```sql
id                   uuid PK default gen_random_uuid()
org_id               uuid NOT NULL FK→orgs(id)
job_assessment_id    uuid NOT NULL FK→job_assessments(id)
candidate_id         uuid NOT NULL FK→candidates(id)
candidate_profile_id uuid FK→candidate_profiles(id)
status               text NOT NULL default 'invited'
                     CHECK(status IN ('invited','in_progress','completed','expired'))
invited_at           timestamptz NOT NULL default now()
started_at           timestamptz
completed_at         timestamptz
time_budget_seconds  int NOT NULL
```
RLS: `org_id`

---

### `question_sets`
One per session. Locked before the test link is emailed (M4-F06).

```sql
id                        uuid PK default gen_random_uuid()
org_id                    uuid NOT NULL FK→orgs(id)
session_id                uuid NOT NULL UNIQUE FK→assessment_sessions(id)
generated_at              timestamptz NOT NULL default now()
locked_at                 timestamptz
generation_prompt_version text NOT NULL
```
RLS: `org_id`

---

### `session_questions`
Individual questions within a set. `evaluation` jsonb populated post-submission by the Evaluation Agent.

```sql
id                  uuid PK default gen_random_uuid()
org_id              uuid NOT NULL FK→orgs(id)
question_set_id     uuid NOT NULL FK→question_sets(id)
sequence_no         int NOT NULL
question            jsonb NOT NULL
category            text NOT NULL
target_competencies text[] NOT NULL default '{}'
difficulty          text NOT NULL CHECK(difficulty IN ('easy','medium','hard','expert'))
answer_format       text NOT NULL CHECK(answer_format IN ('multiple_choice','short_text','long_text'))
options             jsonb
answer_text         text
answered_at         timestamptz
evaluation          jsonb
created_at          timestamptz NOT NULL default now()

UNIQUE(question_set_id, sequence_no)
```
`evaluation` jsonb shape: `{ "competency_scores": [{ "competency": str, "score": 1-5, "explanation": str, "evidence": str }] }`

RLS: `org_id`

---

### `question_fingerprints`
Embedding store for no-repeat guarantee (M4-F05). ANN search pre-filtered by `org_id`.

```sql
id                 uuid PK default gen_random_uuid()
org_id             uuid NOT NULL FK→orgs(id)
question_text      text NOT NULL
question_embedding vector(1536) NOT NULL
question_set_id    uuid FK→question_sets(id)
created_at         timestamptz NOT NULL default now()

INDEX hnsw (question_embedding vector_cosine_ops) WITH (m=16, ef_construction=64)
INDEX btree (org_id)
```
RLS: `org_id`

---

### `behavior_profiles`
M7 output: DISC, Big Five, and style inferences from the full submitted answer set.

```sql
id                        uuid PK default gen_random_uuid()
org_id                    uuid NOT NULL FK→orgs(id)
session_id                uuid NOT NULL UNIQUE FK→assessment_sessions(id)
disc_style                jsonb NOT NULL default '{}'
big_five                  jsonb NOT NULL default '{}'
leadership_style          text
decision_style            text
communication_style       text
work_style                text
stress_signal             text
eq_signal                 text
team_compatibility_signal text
created_at                timestamptz NOT NULL default now()
```
RLS: `org_id`

---

### `integrity_flags`
M8 output: one row per detected anomaly. Human reviewer dismisses or confirms.

```sql
id                  uuid PK default gen_random_uuid()
org_id              uuid NOT NULL FK→orgs(id)
session_id          uuid NOT NULL FK→assessment_sessions(id)
session_question_id uuid FK→session_questions(id)
flag_type           text NOT NULL
                    CHECK(flag_type IN ('ai_generated','duplicate_answer','resume_inconsistency','behavioral_anomaly'))
severity            text NOT NULL CHECK(severity IN ('low','medium','high'))
evidence            text NOT NULL
created_at          timestamptz NOT NULL default now()
```
RLS: `org_id`

---

### `hiring_reports`
M9 output: one per session, produced after full evaluation pipeline completes.

```sql
id                      uuid PK default gen_random_uuid()
org_id                  uuid NOT NULL FK→orgs(id)
session_id              uuid NOT NULL UNIQUE FK→assessment_sessions(id)
executive_summary       text
score_rollup            jsonb NOT NULL default '{}'
behavior_profile_id     uuid FK→behavior_profiles(id)
integrity_summary       jsonb NOT NULL default '{}'
salary_band             text
verdict                 text CHECK(verdict IN ('strong_hire','hire','consider','borderline','reject'))
ai_confidence_score     numeric(5,2) CHECK(ai_confidence_score BETWEEN 0 AND 100)
recommended_next_round  text
training_needs          text[] NOT NULL default '{}'
suggested_hr_questions  text[] NOT NULL default '{}'
suggested_ceo_questions text[] NOT NULL default '{}'
reviewer_override       jsonb
created_at              timestamptz NOT NULL default now()
```
RLS: `org_id`

---

### `competency_library`
M1-F02: reusable competency definitions managed by org Admin.

```sql
id           uuid PK default gen_random_uuid()
org_id       uuid NOT NULL FK→orgs(id)
name         text NOT NULL
description  text
rubric_notes text
created_by   uuid NOT NULL FK→users(id)
created_at   timestamptz NOT NULL default now()

UNIQUE(org_id, name)
```
RLS: `org_id`

---

### `prompt_templates`
M12-F02: versioned prompt templates. `org_id IS NULL` = global platform default visible to all tenants.

```sql
id            uuid PK default gen_random_uuid()
org_id        uuid FK→orgs(id)
agent_name    text NOT NULL
version       text NOT NULL
template_body text NOT NULL
is_active     boolean NOT NULL default false
created_at    timestamptz NOT NULL default now()

UNIQUE(org_id, agent_name, version)
```
RLS policy: `org_id = current_org_id OR org_id IS NULL`

---

### `audit_logs`
Append-only event log. App DB role: INSERT only.

```sql
id           uuid PK default gen_random_uuid()
org_id       uuid NOT NULL FK→orgs(id)
actor_id     uuid NOT NULL
action       text NOT NULL
entity_type  text NOT NULL
entity_id    uuid NOT NULL
metadata     jsonb NOT NULL default '{}'
created_at   timestamptz NOT NULL default now()
```
`actor_id` references `users.id`, `candidates.id`, or `clients.id` depending on `entity_type` — polymorphic, no FK enforced at DB level to allow any identity type.

RLS: `org_id`

---

## Migration Strategy

1. Single Alembic revision: `0001_initial_schema`
2. Order: `orgs` → `users` → `job_assessments` → `candidates` → `clients` → `candidate_profiles` → `assessment_sessions` → `question_sets` → `session_questions` → `question_fingerprints` → `behavior_profiles` → `integrity_flags` → `hiring_reports` → `report_shares` → `competency_library` → `prompt_templates` → `audit_logs`
3. `CREATE EXTENSION IF NOT EXISTS pgvector` at top of migration
4. RLS policies applied in the same migration, after table creation
5. GRANT INSERT only on `audit_logs` to app role after table creation

---

## Out of Scope (this phase)

- Alembic `env.py` wiring (separate `scaffold` session)
- FastAPI model classes beyond SQLAlchemy ORM (separate session)
- Seed data, fixtures, or test factories

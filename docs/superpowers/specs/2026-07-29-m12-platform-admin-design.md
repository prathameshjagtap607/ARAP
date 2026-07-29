# M12 Platform Administration — Design Spec
**Date:** 2026-07-29  
**PRD ref:** Section 16 M12 (F01–F04)  
**Task:** TASK-005 Phase 5  
**Status:** Approved — ready for implementation planning

---

## 1. Objective

Build the Super Admin layer that lets Fidelitus operators manage tenants, control prompt versions, configure model routing per agent, and monitor system health — all without a redeploy.

Exit criteria:
- Prompt version rollback completes without downtime (atomic DB transaction)
- Model routing change takes effect within 30s of PATCH (one Redis TTL cycle), no redeploy
- System health dashboard surfaces queue depth, latency p50/p95/p99, agent error rates, fraud-flag false-positive tracking

---

## 2. Auth — `super_admin` Role

Add `super_admin` to the `ck_users_role` check constraint (migration 0007). A super admin is a real User row belonging to a seeded "system" org so the FK constraint holds.

New dependency in `src/modules/auth/dependencies.py`:

```python
def require_super_admin(claims: TokenClaims = Depends(get_claims)) -> TokenClaims:
    if claims.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return claims
```

All `/admin/*` routes use this dependency exclusively. No existing routes change.

---

## 3. Module Layout

```
services/orchestrator-api/src/modules/admin/
  __init__.py
  router.py          # mounts sub-routers at /admin/tenants, /admin/prompts, /admin/routing, /admin/health
  tenants/
    __init__.py, router.py, service.py, schemas.py
  prompts/
    __init__.py, router.py, service.py, schemas.py
  routing/
    __init__.py, router.py, service.py, schemas.py
  health/
    __init__.py, router.py, service.py, schemas.py
```

`main.py` gets one addition:
```python
from src.modules.admin.router import router as admin_router
app.include_router(admin_router)
```

---

## 4. Data Models — Migration 0007

### 4.1 `users` role constraint
```sql
ALTER TABLE users DROP CONSTRAINT ck_users_role;
ALTER TABLE users ADD CONSTRAINT ck_users_role
    CHECK (role IN ('user', 'admin', 'super_admin'));
```

### 4.2 `orgs` extensions
```sql
ALTER TABLE orgs ADD COLUMN workspace_limit INT NOT NULL DEFAULT 5;
ALTER TABLE orgs ADD COLUMN is_active BOOL NOT NULL DEFAULT true;
ALTER TABLE orgs ADD COLUMN suspended_at TIMESTAMPTZ;
```

### 4.3 New `model_routing_configs` table
```sql
CREATE TABLE model_routing_configs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name        VARCHAR NOT NULL,
    provider          VARCHAR NOT NULL,       -- 'anthropic' | 'openai'
    model_id          VARCHAR NOT NULL,       -- e.g. 'claude-sonnet-5', 'gpt-4o'
    fallback_provider VARCHAR,
    fallback_model_id VARCHAR,
    is_active         BOOL NOT NULL DEFAULT true,
    updated_by        UUID REFERENCES users(id),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_routing_agent UNIQUE (agent_name)
);
```

Valid `agent_name` values: `question_generator`, `report_writer`, `scorer`.

### 4.4 `assessment_sessions` traceability column
```sql
ALTER TABLE assessment_sessions
    ADD COLUMN prompt_template_id UUID REFERENCES prompt_templates(id);
```

Every question generation call writes the active `prompt_template_id` it used. Required by PRD Section 10 (Observability): every generated question/score must be traceable to the exact prompt version that produced it.

### 4.5 `prompt_templates` — no schema change
Existing model is correct: `(org_id, agent_name, version, template_body, is_active)`. `org_id=NULL` means global default; org-scoped rows override global.

---

## 5. API Endpoints

All endpoints require `require_super_admin`. Prefix: `/admin`.

### F01 — Tenant & Workspace Management
```
GET    /admin/tenants                 list all orgs with usage stats (user count, session count)
GET    /admin/tenants/{org_id}        org detail + current usage
POST   /admin/tenants                 provision new org (name, plan_tier, workspace_limit)
PATCH  /admin/tenants/{org_id}        update plan_tier, workspace_limit, is_active
DELETE /admin/tenants/{org_id}/suspend set suspended_at=now(), is_active=false
```

### F02 — Prompt Library Management
```
GET    /admin/prompts                         list all templates across all orgs and agents
GET    /admin/prompts/{agent_name}            all versions for one agent (sorted by created_at desc)
POST   /admin/prompts                         create new version (body: org_id?, agent_name, version, template_body)
POST   /admin/prompts/{id}/activate           activate this version; deactivates current active for same (org_id, agent_name)
POST   /admin/prompts/{id}/rollback           activate the most-recent previously-active version for same (org_id, agent_name)
GET    /admin/prompts/{id}/audit              sessions that used this prompt version (joins assessment_sessions)
```

Activate and rollback are single atomic DB transactions — no in-flight session is interrupted.

### F03 — Model Routing Configuration
```
GET    /admin/routing                         all agent routing configs
PATCH  /admin/routing/{agent_name}            update provider/model/fallback; invalidates Redis cache immediately
POST   /admin/routing/{agent_name}/test       dry-run invocation to verify new config (returns provider, model used, latency)
```

### F04 — System Health & Incident Monitoring
```
GET    /admin/health/overview         queue depth, error rate, p50/p95/p99 latency (last 24h from DB)
GET    /admin/health/incidents        agent errors grouped by type, last 7 days
GET    /admin/health/fraud-flags      integrity_flags counts, false-positive rate (flagged candidates who were hired)
```

Metrics are derived from existing tables (no new infrastructure):
- Latency: `assessment_sessions.completed_at - started_at`
- Queue depth: Redis list length for the generation queue key
- Error rate: sessions with `status='error'` / total sessions in window
- Fraud false-positives: `integrity_flags` joined with `hiring_reports` (flagged + hired = false positive)

---

## 6. Model Routing Cache

`get_routing_config(agent_name: str)` in `routing/service.py`:

1. Check Redis key `routing:{agent_name}` (TTL 30s)
2. On miss: SELECT from `model_routing_configs` WHERE `agent_name=? AND is_active=true`; write to Redis
3. `PATCH /admin/routing/{agent_name}` updates DB + calls `redis.delete(f"routing:{agent_name}")` immediately

Maximum propagation delay: 30s. No redeploy required.

**Fallback behaviour:** if primary provider returns HTTP 5xx or times out, agent retries once with `fallback_provider`/`fallback_model_id`. If fallback also fails, error is logged and surfaces in F04 incidents.

---

## 7. `packages/prompt-library` (TypeScript)

Populate `src/index.ts` with:
- `AGENT_NAMES` const array: `['question_generator', 'report_writer', 'scorer']`
- `PromptVersion` type: `{ id: string; agentName: string; version: string; isActive: boolean; createdAt: string }`
- `ModelRoutingConfig` type: `{ agentName: string; provider: string; modelId: string; fallbackProvider?: string; fallbackModelId?: string }`

Frontend imports these to avoid stringly-typed agent names.

---

## 8. Frontend — `apps/console-web`

New page group `src/app/(console)/admin/` with four tabs mirroring M11 analytics pattern:
- **Tenants** tab — table of orgs with plan tier, usage, suspend action
- **Prompt Library** tab — version list per agent, activate/rollback buttons, audit drawer
- **Model Routing** tab — one row per agent, inline edit for provider/model, test button
- **System Health** tab — stat tiles (queue depth, error rate), latency p50/p95/p99 chart, incidents list

Route guard: redirect non-super-admin users to `/dashboard`.

---

## 9. Testing

```
tests/admin/test_tenants.py    CRUD + suspend flow
tests/admin/test_prompts.py    create version, activate, rollback, audit join
tests/admin/test_routing.py    cache invalidation (mock Redis), fallback routing
tests/admin/test_health.py     fixture data → correct aggregates
```

Pattern matches existing `tests/<module>/test_<feature>.py` conventions. All tests use the real test DB (no mocks for DB per project feedback).

---

## 10. Open Questions (PRD §18, carried forward)

- **#3 LLM provider selection per agent** — `model_routing_configs` seeds with placeholder values; finalize against cost/latency benchmarking before go-live. The UI must not hardcode a single provider.
- **#5 Human calibration set size** — not needed for M12; flagged in M11 health metric for inter-rater agreement. No action here.

---

## 11. Out of Scope

- Billing/payment integration — plan_tier is a string label only; no Stripe wiring
- ATS integrations (PRD §18 open question #6)
- Predictive modeling (M11-F05 v2, PRD §17)

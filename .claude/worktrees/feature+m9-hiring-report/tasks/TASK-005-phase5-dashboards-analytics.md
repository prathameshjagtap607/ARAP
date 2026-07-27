# TASK-005 — Phase 5: Analytics & Scale

**PRD ref:** Section 16, Phase 5 (Weeks 23–26)
**Owner:** Srinivas / Fidelitus Corp
**Status:** Not started
**Depends on:** TASK-001, TASK-002 (needs real session/report data to
analyze and dashboard)

## Objective

Round out the platform surfaces that sit on top of a working pipeline:
full dashboards, org-wide analytics, and platform administration
(prompt/model routing, tenant management). Note: PRD §16 also lists
competency library/templates (M1-F02/F03) and Admin/Reports dashboards here,
but those were pulled forward into TASK-001/TASK-000 where more natural —
this task covers what's left: M10 (remaining), M11 (full), M12 (full).

## Scope (modules)

- **M10 — Dashboards, remaining**: Admin Dashboard (F03), Reports Dashboard
  (F04) — HR and Candidate dashboards already exist from TASK-001
- **M11 — Analytics** (F01–F05): score trends, hiring funnel, question &
  difficulty analytics, candidate benchmarking, skill trend surfacing
  (predictive hiring-success modeling is v2+, PRD §17 — stub data model only)
- **M12 — Platform Administration** (F01–F04): tenant/workspace management,
  prompt library management with versioning + rollback, model routing
  configuration per agent, system health/incident monitoring

## Out of scope

- Predictive on-the-job success modeling (M11-F05 v2, needs historical hire
  outcomes — PRD §17)
- ATS integrations (Greenhouse/Lever/Workday) — no ATS confirmed for MVP
  (PRD §18 open question #6)

## Related sessions (arap-sessions.ps1)

`dashboards`, `analytics`, `admin`

## Exit criteria

- [ ] Admin Dashboard shows org users/roles, competency library, templates,
      billing/plan status
- [ ] Reports Dashboard is searchable/filterable by verdict and score band
- [ ] All four Analytics views (score trends, funnel, question/difficulty,
      benchmarking) load from real session data, correctly org-scoped
- [ ] Expensive aggregates cached in Redis; dashboard initial load < 2s
- [ ] Prompt Library supports versioned rollout/rollback per tenant or
      globally, with every generated question/score traceable to the exact
      prompt version used (PRD §10 Observability)
- [ ] Model Routing config change takes effect on next agent invocation
      without a redeploy, with fallback routing on provider outage
- [ ] System Health dashboard surfaces queue depth, p50/p95/p99 generation
      latency, agent error rates, fraud false-positive tracking

## Open questions (PRD §18)

- **#3 LLM provider selection per agent** — should be finalized against cost/
  latency benchmarking before this task locks in default Model Routing
  config; don't hardcode a single provider assumption into the UI.
- **#5 Human calibration set size** — needed to validate the >75% inter-rater
  agreement metric surfaced in Analytics; sourcing (pilot org volunteers vs.
  synthetic) not yet decided — flag as an open item rather than fabricating
  a number.

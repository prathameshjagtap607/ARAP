# TASK-000 — Phase 0: Foundation

**PRD ref:** Section 16, Phase 0 (Weeks 1–3)
**Owner:** Srinivas / Fidelitus Corp
**Status:** Not started

## Objective

Stand up the repo, data model, auth/RBAC, and both frontend shells so every
later module has a working foundation to build on. No AI agents run yet.

## Scope

- Repository scaffold per PRD §11.2 (monorepo: `apps/`, `services/`, `agents/`,
  `packages/`, `infra/`)
- Data model per PRD §12 (all tables listed there, in PostgreSQL + pgvector)
- Auth + RBAC per PRD §4 and §15 (Admin/User password login; Candidate/Client
  passwordless magic-link/OTP, session- and report-scoped JWTs)
- `candidate-web` and `console-web` Next.js app shells (empty nav, theming,
  typed API client, route guards mirroring server RBAC)
- CI: lint + test + build green; `docker-compose.yml`; `.env.example`

## Out of scope (do not build yet)

- Any of the 8 AI agents (§7) — agent folders are skeleton-only at this stage
- Job Assessment Builder, resume ingestion, or any M1–M12 feature logic
- Dashboards beyond an empty authenticated shell

## Related sessions (arap-sessions.ps1)

- `schema` — tables per §12
- `scaffold` — repo layout + FastAPI/Next.js bootstrap
- `auth` — 4-identity auth + RBAC + JWT scoping
- `frontend-console` — console-web shell
- (frontend-candidate shell also references this task for its initial
  scaffold pass, though its main build happens under TASK-001)

## Exit criteria

- [ ] All tables from PRD §12 exist as migrations, org_id scoping + RLS in place
- [ ] pgvector extension enabled, `question_fingerprints.question_embedding`
      indexed
- [ ] Admin/User login (password) and Candidate/Client login (passwordless,
      scoped JWT) all working and tested
- [ ] A Candidate JWT cannot access any `assessment_session` other than its own
      (manually verified)
- [ ] Both app shells boot, authenticate, and route-guard by role
- [ ] CI pipeline green (lint, test, build) on a clean checkout

## Open questions

- None blocking Phase 0. (See PRD §18 for platform-wide open questions —
  none apply to foundation work.)

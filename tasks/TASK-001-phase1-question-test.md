# TASK-001 — Phase 1: MVP — Question Generation & Test Delivery

**PRD ref:** Section 16, Phase 1 (Weeks 4–8)
**Owner:** Srinivas / Fidelitus Corp
**Status:** Not started
**Depends on:** TASK-000 (foundation must be complete)

## Objective

Ship the core MVP loop end to end: recruiter defines a job → candidate's
resume is parsed and profiled → AI generates a locked, personalized question
set → candidate takes the test via emailed link → answers are scored → a
basic hiring report with a verdict is produced. This is the smallest slice
of ARAP that is actually usable on a live requisition.

## Scope (modules)

- **M1 — Job Assessment Builder** (F01–F04): assessment creation, competency
  library, templates/cloning, candidate invitation → `assessment_session`
- **M2 — Resume & Profile Ingestion** (F01–F04): multi-format upload, Resume
  Analysis Agent extraction, GitHub/portfolio enrichment, resume-to-JD match
- **M3 — Candidate Profile Engine** (F01–F04): summary, skill matrix, career/
  leadership estimate, strength/risk flagging
- **M4 — Question Generation Engine** (F01–F06): upfront batch generation,
  category coverage, resume-referenced questions, risk-flag targeting,
  no-repeat fingerprinting, set lock
- **M5 — Test Delivery** (F01–F05): emailed link, DISC-style runtime, answer
  formats (MCQ/short/long text only), time-bound window, save & resume
- **M6 — Evaluation Engine** (F01–F04): batch scoring, evidence citation,
  session roll-up, human override/calibration capture
- **M9 — Hiring Report Generator**: **basic only** (F01 executive summary +
  verdict, F02 report sections) — no behavior inference, no fraud detection
  yet (that's TASK-002)
- **M10 — Dashboards**: HR Dashboard (F01) and Candidate Dashboard (F02) only,
  just enough to see sessions move through the pipeline
- Candidate-facing frontend (`frontend-candidate` shell): login → consent →
  test runtime → status screen

## Out of scope (do not build yet)

- Behavior Inference (M7), Fraud & Integrity Detection (M8) — TASK-002
- Full report enrichment (Integrity Summary, behavior profile in report) —
  TASK-002
- Analytics (M11), Admin console (M12 beyond what auth/RBAC already covers) —
  TASK-005
- Voice/video/coding-sandbox answer formats — deferred per PRD §17

## Related sessions (arap-sessions.ps1)

`job-assessment`, `resume-ingestion`, `candidate-profile`, `question-gen`,
`test-delivery`, `evaluation`, `frontend-candidate`

## Exit criteria

- [ ] Recruiter can create a job assessment with weightage summing to 100%
      (validated server-side)
- [ ] Resume upload → `candidate_profile` produced with per-field confidence
      scores and a resume-to-JD match score
- [ ] Question Generation Agent produces a full locked question set per
      candidate; two sessions for the same role/different candidates share
      **zero** verbatim questions (PRD §3 goal)
- [ ] Question-set generation p95 < 6s per question (PRD §3 goal)
- [ ] Candidate can log in via emailed link, take the test DISC-style, and
      submit within the time window; a simulated disconnect does not lose
      already-answered questions
- [ ] On submission, Evaluation Agent scores every answer with a cited
      excerpt, and a session-level roll-up + basic verdict is produced
- [ ] Basic report visible on the HR Dashboard within 5 minutes of submission
- [ ] Candidate Dashboard never exposes a raw competency score

## Open questions (PRD §18)

- **#1 Salary recommendation data source** — MVP assumes org-provided comp
  bands; do not attempt external salary API integration in this task.

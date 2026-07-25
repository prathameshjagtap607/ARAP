# TASK-002 — Phase 2: Behavioral Intelligence & Integrity

**PRD ref:** Section 16, Phase 2 (Weeks 9–13)
**Owner:** Srinivas / Fidelitus Corp
**Status:** In progress — M7 complete, M8 and M9 remaining
**Depends on:** TASK-001 (MVP loop must be working end to end)

## Objective

Enrich the MVP pipeline with behavioral inference and fraud/integrity
detection, and extend the hiring report to a fully compiled, explainable
document. This is what makes ARAP more than a scored quiz.

## Scope (modules)

- **M7 — Behavior Inference Engine** (F01–F05): DISC style, Big Five,
  leadership/decision/communication/work style, stress & EQ signal, team
  compatibility signal — all inferred from the submitted answer set, never
  from direct self-report questions
- **M8 — Fraud & Integrity Detection** (F01–F05): AI-generated/scripted
  detection, duplicate/near-duplicate answer detection, resume-answer
  consistency check, behavioral signal anomalies (voice/video — stub only,
  no voice/video capture exists yet), integrity summary compilation
- **M9 — Hiring Report Generator, full** (extends TASK-001's basic report):
  Recommendation Agent (salary band, verdict synthesis, training needs),
  full report sections including Integrity Summary and behavior profile,
  benchmarking (F03), export/sharing (F04), reviewer feedback loop (F05)
- Report Generator Agent and Recommendation Agent wired into the pipeline in
  the order defined in PRD §11.3: Evaluation → Behavior → Fraud → Scoring →
  Recommendation → Report Generator

## Out of scope

- Actual voice/video capture (M8-F04's audio/video anomaly detection has no
  input to run on until voice/video modalities ship — deferred per §17);
  build the flag *type* and schema now, leave detection logic as a documented
  stub
- Analytics (M11), Admin (M12) — TASK-005

## Related sessions (arap-sessions.ps1)

`behavior-inference`, `fraud-integrity`, `hiring-report`

## Exit criteria

- [x] `behavior_profile` generated for 100% of completed sessions (PRD §3 goal) — M7 COMPLETE (commit a77495c)
- [ ] Fraud checks run against a labeled validation set once available;
      recall > 85%, false-positive < 10% (PRD §3 goal — see open question #4
      below if the labeled set doesn't exist yet)
- [ ] Integrity Summary appears in every report with severity + evidence,
      never an automatic reject on its own
- [ ] Full report includes all sections from PRD §M9-F02; every score is
      traceable to a quoted answer excerpt
- [ ] Low AI Confidence Score reports are visually flagged and route to
      mandatory human review (PRD §9.4, §15)
- [ ] Recruiter can override any AI score or the final verdict; overrides are
      captured for the calibration dataset (M6-F04, M9-F05)
- [ ] Report export to PDF and scoped expiring share link both work

## Open questions (PRD §18)

- **#4 Fraud detection false-positive tolerance** — sourcing/labeling a
  validation dataset is a prerequisite for validating the recall/FP targets;
  if no labeled set exists yet, flag this explicitly rather than reporting a
  false pass.
- **#2 Video/emotion analysis scope** — confirm the biometric/emotion
  exclusion (PRD §15) against jurisdiction-specific algorithmic-hiring rules
  before any future video work begins; not blocking for this task since no
  video capture exists yet.

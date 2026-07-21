# PRD — AI Recruitment Assessment Platform (ARAP)

**Version:** 1.0
**Date:** 20 July 2026
**Owner:** Srinivas / Fidelitus Corp
**Status:** Draft — Ready for Review
**Build model:** Solo developer + Claude Code CLI
**Development Environment:** Claude Code CLI (local) → Cloud

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [Users & Roles](#4-users--roles)
5. [Information Architecture](#5-information-architecture)
6. [Complete Feature Specification](#6-complete-feature-specification)
   - [M1 — Job Assessment Builder](#m1--job-assessment-builder)
   - [M2 — Resume & Profile Ingestion](#m2--resume--profile-ingestion)
   - [M3 — Candidate Profile Engine](#m3--candidate-profile-engine)
   - [M4 — Question Generation Engine](#m4--question-generation-engine)
   - [M5 — Test Delivery](#m5--test-delivery)
   - [M6 — Evaluation Engine](#m6--evaluation-engine)
   - [M7 — Behavior Inference Engine](#m7--behavior-inference-engine)
   - [M8 — Fraud & Integrity Detection](#m8--fraud--integrity-detection)
   - [M9 — Hiring Report Generator](#m9--hiring-report-generator)
   - [M10 — Dashboards](#m10--dashboards)
   - [M11 — Analytics](#m11--analytics)
   - [M12 — Platform Administration](#m12--platform-administration)
7. [AI Agent Architecture](#7-ai-agent-architecture)
8. [Question Generation & Test Flow](#8-question-generation--test-flow)
9. [Scoring & Evaluation Framework](#9-scoring--evaluation-framework)
10. [Non-Functional Requirements](#10-non-functional-requirements)
11. [Technical Architecture](#11-technical-architecture)
12. [Data Model](#12-data-model)
13. [REST API Design](#13-rest-api-design)
14. [Key User Flows](#14-key-user-flows)
15. [Security, Privacy & Compliance](#15-security-privacy--compliance)
16. [Development Phases](#16-development-phases)
17. [Future Enhancements](#17-future-enhancements)
18. [Open Questions & Assumptions](#18-open-questions--assumptions)

---

## 1. Executive Summary

**ARAP (AI Recruitment Assessment Platform)** is a multi-tenant SaaS product that replaces static interviews and personality questionnaires with an AI-generated, personalized assessment: it reads the job requirement (entered by the recruiter) and the candidate's resume, and **generates a complete, personalized set of questions upfront** for that candidate alone. The candidate takes this as a self-paced test — delivered as a link by email, taken in a familiar DISC-style format (question by question, select/submit answers, no live back-and-forth). Once submitted, the AI evaluates every answer across technical and behavioral competencies, infers a personality/behavioral profile from the answer set, screens for anomalies, and produces an evidence-backed, HR-ready hiring report with a final verdict.

The platform is **not a plain DISC tool**. DISC-style traits (style, communication, decision pattern, stress handling) are one inferred output among many — technical depth, leadership readiness, culture fit, risk areas, and a hiring recommendation are the primary product. No two candidates ever receive the same question set: every question set is generated fresh from the job profile and that candidate's own parsed resume before the test is sent out.

The system is organized around a **linear assessment pipeline** (Job Assessment → Resume Ingestion → Candidate Profile → Question Generation → Test Delivery (email link) → Evaluation → Behavior Inference → Fraud Check → Report) surfaced through **four dashboards** (HR, Candidate, Admin, Analytics) and driven by **seven cooperating AI agents**.

This is not a prototype. Every feature in this document is intended to ship as a complete, role-secured module before the platform is used on a live requisition.

---

## 2. Problem Statement

### 2.1 Current State

Recruitment assessment today is fragmented and inconsistent:

- **Every candidate for a role gets the same question bank.** Candidates share and memorize answers on Glassdoor, Reddit, and internal forums, so the interview stops measuring anything real.
- **Interview quality is interviewer-dependent.** A strong interviewer probes deeply; a weak one asks surface questions and rubber-stamps a gut feeling.
- **Competencies are assessed in silos.** Technical skill is tested in one round, leadership in another, personality in a separate DISC/psychometric tool — nothing ties them to a single evidence trail or a single score.
- **Personality tools are self-report and gameable.** Candidates answer DISC/Big-Five questionnaires the way they believe the employer wants, not the way they behave.
- **Hiring reports are unstructured.** Panel notes are inconsistent in depth, format, and rigor; comparing two candidates for the same role is subjective.
- **Resume signal is wasted.** Resumes are skimmed for keywords, not mined for career trajectory, project depth, or risk indicators that should shape the interview itself.

### 2.2 Root Causes

1. **No personalized question generation** — question banks are static and pre-written, not derived from the specific job and candidate in front of the interviewer.
2. **No unified evaluation model** — technical, behavioral, and leadership assessment run on different tools with no shared scoring rubric.
3. **No behavioral inference from natural conversation** — personality is measured by asking about it directly, which invites impression management.
4. **No fraud/integrity signal** — no detection of AI-generated, scripted, or copied answers, or of resume-to-answer inconsistency.
5. **No standardized, explainable hiring report** — recommendations are not evidence-linked, so two reviewers cannot audit *why* a verdict was reached.

### 2.3 What ARAP Solves

A single platform where HR defines a job assessment once; the AI reads the candidate's resume and the recruiter's skill/requirement input and generates a personalized question set upfront, unique to that candidate; the candidate takes the test at their own pace via an emailed link, in a static, DISC-style question-and-answer format; once submitted, every answer is scored against an explicit multi-competency rubric by the AI; behavioral and leadership traits are inferred from the answer set; fraud and inconsistency signals are surfaced automatically; and a structured, explainable hiring report with a final verdict (Strong Hire / Hire / Consider / Borderline / Reject) is produced for HR and the CEO without manual compilation.

---

## 3. Goals & Success Metrics

| Goal | Metric | Target |
|------|--------|--------|
| Question uniqueness | Two assessments (same role, different candidates) sharing an identical question | 0% verbatim overlap |
| Personalization | Question sets generated from that candidate's own resume + job requirements | 100% of sessions |
| Evaluation coverage | Competencies scored per completed test (technical, behavioral, leadership, communication) | 100% |
| Behavioral inference | Sessions producing DISC + Big Five + leadership style from the answer set, without the candidate ever being asked to self-report | 100% |
| Fraud detection | Sessions flagged for AI-generated/copied/scripted answers, false positive rate | Recall > 85%, false-positive < 10% (validated on labeled test set) |
| Report turnaround | Time from interview completion to final report available | < 5 minutes |
| Report explainability | Every competency score traceable to at least one cited answer excerpt | 100% |
| HR adoption | Assessments created and completed fully in-platform (no manual notes) | > 90% within 60 days of rollout |
| Reviewer agreement | Inter-rater agreement between AI verdict and human panel verdict (calibration set) | > 75% within one verdict band |
| Performance | API p95 response time (non-generative endpoints) | < 400 ms |
| Generative latency | Time to generate a candidate's full question set | < 6 s p95 per question, batch completes within target |
| Reliability | Platform uptime | 99.5% monthly |
| Security | Role isolation enforced; zero cross-tenant data leakage | Penetration tested |

---

## 4. Users & Roles

### 4.1 Role Definitions

**Admin** — creates and manages User accounts, manages company workspace (departments, competency libraries, culture-value definitions, billing), has full visibility across all assessments, candidates, and reports created by any User.

**User** — creates job assessments, uploads candidate resumes, sends assessment invites to Candidates and Clients, reviews interview transcripts and reports, records final hiring decisions, reviews AI verdicts.

**Candidate** — a lightweight authenticated identity, not a full workspace user. Receives an assessment invite by email; the invite link requires the candidate to log in (passwordless — magic link or OTP tied to the invited email, or set-password-on-first-click) before the exam becomes accessible. Once logged in, the candidate uploads resume/portfolio links, completes the interview, and views only their own status (never internal scores). A candidate's login is scoped to the single `assessment_session` they were invited to — it is not a general platform account with cross-session access.

**Client** — a lightweight authenticated identity, not a full workspace user. Receives a scoped invite/share link by email; login (same passwordless mechanism as Candidate) is required before the shared report becomes viewable. A client's login is scoped only to the specific report(s) explicitly shared with them by a User — never a general account with visibility into other candidates, sessions, or reports.

Candidates and Clients do not have full workspace accounts (no password-based admin-console login, no membership in `users`), but they do now authenticate before accessing their respective scoped resource (exam or report) rather than accessing it directly off an unauthenticated link.

### 4.2 Access Control Matrix (summary)

| Capability | Candidate | Client | User | Admin |
|---|---|---|---|---|
| Login required before resource access | ✅ (passwordless, session-scoped) | ✅ (passwordless, report-scoped) | ✅ (password) | ✅ (password) |
| Create job assessment | – | – | ✅ | ✅ |
| Upload own resume | ✅ | – | ✅ (on behalf) | ✅ (on behalf) |
| Take interview | ✅ (own invited session only) | – | – | – |
| View own interview scores | – | – | ✅ | ✅ |
| View full hiring report | – | ✅ (only reports explicitly shared with them) | ✅ | ✅ |
| Override/annotate AI verdict | – | – | ✅ | ✅ |
| Manage competency libraries | – | – | – | ✅ |
| Manage users | – | – | – | ✅ |
| View cross-org/all-user analytics | – | – | – | ✅ |

Tenant isolation is enforced at the database and API layer: no query ever crosses `org_id` boundaries except for the Admin role. Candidate and Client logins are additionally scoped below the org level — to a single `assessment_session` (Candidate) or a single set of explicitly-shared `hiring_reports` (Client) — never to the org's data as a whole.

---

## 5. Information Architecture

The platform is organized around **twelve modules**, grouped into a linear assessment pipeline (M1–M9) and three cross-cutting surfaces (M10–M12):

**Pipeline:**
1. **M1 — Job Assessment Builder** — HR defines the role, competencies, and weighting.
2. **M2 — Resume & Profile Ingestion** — parse resume, LinkedIn, GitHub, portfolio.
3. **M3 — Candidate Profile Engine** — synthesizes parsed data into a structured candidate profile.
4. **M4 — Question Generation Engine** — generates the full, personalized question set upfront, before the test is sent.
5. **M5 — Test Delivery** — emailed test link; static, DISC-style, self-paced question-and-answer runtime.
6. **M6 — Evaluation Engine** — scores every submitted answer against the rubric after submission.
7. **M7 — Behavior Inference Engine** — infers DISC/Big Five/leadership/EQ from conversation.
8. **M8 — Fraud & Integrity Detection** — flags anomalies across the session.
9. **M9 — Hiring Report Generator** — compiles the final HR-ready report and verdict.

**Cross-cutting:**
10. **M10 — Dashboards** — HR, Candidate, Admin, Reports.
11. **M11 — Analytics** — org-wide, department-wide, role-wide trend and benchmark views.
12. **M12 — Platform Administration** — tenants, prompts, model routing, competency libraries.

---

## 6. Complete Feature Specification

---

## M1 — Job Assessment Builder

### M1-F01 — Job Assessment Creation

Recruiter defines a new assessment with: company, department, job role/title, experience required (min/max years), required skills, preferred skills, responsibilities, education requirements, certifications, behavioral competencies to assess, leadership competencies to assess, organizational culture values, difficulty level (Junior/Mid/Senior/Executive), target interview duration, and per-competency assessment weightage (must sum to 100%).

Output: a structured `job_assessment` record used as the grounding context for every AI agent downstream (question generation, evaluation, report benchmarking).

### M1-F02 — Competency Library

Org Admin maintains reusable competency definitions (e.g., "Stakeholder Management," "Cloud Cost Optimization") with a rubric description, so recruiters compose assessments from a vetted library rather than free-typing criteria each time. Custom one-off competencies are still allowed per assessment.

### M1-F03 — Assessment Templates & Cloning

Recruiters can save an assessment as a reusable template per role family (e.g., "Senior IT Manager — India") and clone it for future requisitions, adjusting weightage and skills without rebuilding from scratch.

### M1-F04 — Candidate Invitation

Recruiter invites one or more candidates to a created assessment via email/link. Each invitation is a distinct `assessment_session` scoped to one candidate, one job assessment, one resume upload — ensuring question generation is always 1:1:1.

---

## M2 — Resume & Profile Ingestion

### M2-F01 — Multi-Format Resume Upload

Accepts PDF, DOCX, and plain text resumes; accepts LinkedIn profile URL, GitHub username/URL, and personal portfolio/website URL. Files are parsed synchronously (<10s target) with a job queue fallback for larger documents.

### M2-F02 — Resume Parsing Extraction

The Resume Analysis Agent extracts: skills (explicit and inferred), projects, technologies used, employment history, education, certifications, achievements/quantified impact, leadership indicators (team size, scope of ownership), career timeline (including gaps, with gap length and count), domain keywords, and a parsing confidence score per field (to flag ambiguous or low-quality resumes).

### M2-F03 — GitHub / Portfolio Enrichment

Where a GitHub handle or portfolio URL is supplied, the agent pulls public repository metadata (languages, commit recency, README quality, pinned projects) and portfolio case studies to corroborate or extend resume claims. This enrichment is additive evidence only — never a hard gate.

### M2-F04 — Resume-to-JD Match Score

Computes a semantic match score (embeddings-based) between the parsed resume and the job assessment's required/preferred skills and responsibilities, surfaced to the recruiter before the interview is scheduled and used as an input signal (not the sole input) to initial interview difficulty.

---

## M3 — Candidate Profile Engine

### M3-F01 — Candidate Summary Generation

Synthesizes a narrative candidate summary (2–3 paragraphs) covering current role, career trajectory, standout achievements, and domain fit, generated by the Job Description Agent + Resume Analysis Agent jointly against the specific job assessment.

### M3-F02 — Skill & Experience Matrix

Tabular view mapping each required/preferred skill from the job assessment to: evidence found in resume (yes/partial/no), years of applied experience (estimated), and confidence.

### M3-F03 — Career Growth & Leadership Level Estimate

Estimates career velocity (time-to-promotion pattern), current leadership level (IC / Team Lead / Manager / Director / VP-equivalent), and scope (team size, budget, geography) purely from resume signal — refined later by interview evidence.

### M3-F04 — Strength / Risk Area Flagging

Flags candidate strengths (e.g., "deep AWS cost-optimization experience") and risk areas (e.g., "no direct people-management despite Manager title," "18-month unexplained gap in 2022") that seed targeted interview questions in M4.

---

## M4 — Question Generation Engine

### M4-F01 — Upfront Personalized Question Generation

Once the candidate's resume is parsed (M2/M3) and the job assessment is defined (M1), the Question Generation Agent produces the **complete question set for that candidate in a single batch**, combining: the job assessment (required/preferred skills, responsibilities, difficulty level), the candidate profile (M3 — resume-derived skills, experience, strengths, risk flags), and the target question-category mix. This generation happens once, before the test is sent — there is no live, in-session regeneration or difficulty adaptation based on how the candidate answers.

### M4-F02 — Question Category Coverage

Ensures the generated set has balanced coverage across configured question categories: Technical, Behavioral, Leadership, Case Study, Scenario, Decision-Making, Conflict Resolution, Problem Solving, Analytical, Situational Judgment, Communication, Ethics, Innovation, Culture Fit, Stress, Priority Management, Negotiation, Business Strategy, Financial, Presentation, Customer Handling — weighted by the job assessment's competency weightage (M1-F01), not asked uniformly.

### M4-F03 — Resume-Referenced Questions

At least one question in every generated set must reference the candidate's resume directly (e.g., "Your resume states you led a 12-person team — walk me through a specific conflict you resolved within that team."), so the set is verifiably personalized and not generic.

### M4-F04 — Risk-Flag Targeted Questions

Strength/risk flags surfaced by the Candidate Profile Engine (M3-F04) are used to seed specific questions in the generated set (e.g., probing an unexplained resume gap, or a claimed skill with weak supporting evidence).

### M4-F05 — No-Repeat Guarantee

Maintains a semantic fingerprint (embedding) of every question generated for a candidate and rejects/regenerates any question above a similarity threshold, guaranteeing no repeated or near-duplicate question within a candidate's set or across a candidate's historic sessions with the same org.

### M4-F06 — Set Finalization & Lock

Once the question set is generated and the test invite is sent, the set is locked for that `assessment_session` — it does not change based on anything that happens after the email goes out, ensuring every candidate answers the exact set they were sent.

---

## M5 — Test Delivery

### M5-F01 — Emailed Test Link

Once the question set (M4) is generated, the candidate receives an email containing a scoped test link tied to their `assessment_session`. Clicking it starts the login flow (§4.1) before the test becomes accessible.

### M5-F02 — DISC-Style Test Runtime

After login, the candidate takes the test in a static, self-paced, question-and-answer format — the same familiar experience as a DISC questionnaire: questions are presented (one at a time or as a paginated set), the candidate selects/enters their answer for each, can move between questions before submitting, and submits the whole set at the end. There is no live AI interaction, no adaptive branching, and no synchronous session with the AI during the test itself.

### M5-F03 — Answer Formats

Supports the answer formats appropriate to each generated question: multiple-choice/select, short text response, and long-form text response. (Voice/video/live-interview and coding-sandbox modalities are deferred — see §17.)

### M5-F04 — Time-Bound Test Window

The test enforces the job assessment's configured duration (M1-F01) as an overall time limit for the full set, with an on-screen timer; auto-submits whatever has been answered when time expires.

### M5-F05 — Save & Resume

Candidate progress is saved after each answered question, so a transient disconnect does not lose answers already submitted within the session.

---

## M6 — Evaluation Engine

### M6-F01 — Post-Submission Batch Scoring

Once the candidate submits the completed test (M5), the Evaluation Agent scores every answer in the set against the full competency rubric (§9): technical accuracy, depth of knowledge, confidence, leadership, communication, logical thinking, critical thinking, business thinking, problem solving, decision making, innovation, risk awareness, ownership, teamwork, conflict handling, customer focus, learning ability, adaptability, culture fit, professionalism — scoring only the competencies relevant to that question's category (not all 20 per answer). This runs as a single batch pass after submission, not turn-by-turn during the test.

### M6-F02 — Explanation & Evidence Citation

Each score is accompanied by a machine-generated explanation quoting the specific part of the candidate's answer that justifies it, plus one explicit strength and one explicit improvement area — ensuring every number in the final report is auditable back to the candidate's submitted answer.

### M6-F03 — Session Roll-Up Scoring

Aggregates per-answer scores into per-competency session scores using the job assessment's weightage (M1-F01), producing the Technical, Leadership, Communication, and Behavior scores that appear in the final report (§9).

### M6-F04 — Calibration Against Human Reviewers

Recruiters can override/annotate any AI score with their own rating and comment; these overrides are captured as labeled training/calibration data to tune future prompt versions and are surfaced in Analytics (M11) as the AI/human agreement metric (§3).

---

## M7 — Behavior Inference Engine

### M7-F01 — DISC Style Inference

Infers the candidate's dominant DISC style(s) from language patterns, decision framing, and response structure across the candidate's full set of submitted answers — never from direct "which of these describes you" questions.

### M7-F02 — Big Five Trait Inference

Infers Openness, Conscientiousness, Extraversion, Agreeableness, and Neuroticism/Emotional Stability from conversational evidence (e.g., handling of ambiguity, structure of answers, response to pushback).

### M7-F03 — Leadership, Decision, Communication & Work Style

Infers leadership style (e.g., directive vs. coaching), decision-making style (data-driven vs. intuitive), communication style (concise vs. narrative), and general work style (structured vs. exploratory) from patterns observed across multiple answers, not any single question.

### M7-F04 — Stress Handling & Emotional Intelligence

Uses designated Stress-category questions (M4-F02) and observed response degradation/recovery under a deliberately pressured follow-up to infer stress tolerance; infers EQ from how the candidate discusses conflict, feedback, and team friction in Conflict Resolution / Teamwork questions.

### M7-F05 — Team Compatibility Signal

Cross-references inferred style/communication/decision patterns against the hiring team's configured working style (optional org-level input) to produce a compatibility signal, presented as a discussion prompt for the recruiter, not an automated pass/fail.

---

## M8 — Fraud & Integrity Detection

### M8-F01 — AI-Generated / Scripted Response Detection

Flags answers with statistical signatures of AI-generation or memorized/scripted delivery (e.g., unnaturally uniform structure across answers, response latency inconsistent with a live thinking process, phrasing divergent from the candidate's own earlier, more casual answers).

### M8-F02 — Duplicate / Near-Duplicate Answer Detection

Flags answers highly similar to other candidates' answers in the same org/role (embedding similarity across the tenant's historical answer corpus), surfacing possible answer-sharing.

### M8-F03 — Resume-Answer Consistency Check

Cross-checks specific claims made in interview answers against the parsed resume (M2) and flags material contradictions (e.g., claims a technology/project not present anywhere in resume or portfolio evidence, or timeline conflicts).

### M8-F04 — Behavioral Signal Anomalies

For voice/video sessions, flags long unexplained pauses, disclosed-vs-observed confidence mismatch, and multiple-speaker audio detection (possible outside assistance) — these are flags for human review only, never an automatic reject.

### M8-F05 — Integrity Summary in Report

All fraud signals for a session are compiled into an Integrity Summary section of the final report (§M9) with severity (Low/Medium/High) and the specific evidence, so the human reviewer makes the final call.

---

## M9 — Hiring Report Generator

### M9-F01 — Executive Summary & Verdict

Auto-generated 1-paragraph executive summary plus the Final Verdict: **Strong Hire / Hire / Consider / Borderline / Reject**, each backed by the score roll-ups and explicit reasoning, never a bare label.

### M9-F02 — Full Report Sections

Candidate Overview, Resume Summary, Interview Summary, Technical Score, Leadership Score, Communication Score, Behavior Score, Culture Fit, Domain Knowledge, Skill Gap Analysis, Strengths, Weaknesses, Potential Risks, Learning Curve Estimate, Management Readiness, Promotion Potential, Salary Recommendation (band, not a single figure, informed by market data input — see §18 open question), Overall Rating, AI Confidence Score, Recommended Next Interview Round, Training Needs (if hired), Suggested Questions for Final HR Round, Suggested Questions for CEO Round, Integrity Summary (from M8), Final Verdict.

### M9-F03 — Benchmarking Against Job & Org Expectations

Every score is presented not just in absolute terms but relative to the job assessment's required bar and, where available, to the org's historical hiring bar for that role family (from Analytics, M11).

### M9-F04 — Report Export & Sharing

Reports export to PDF and are shareable via a scoped, expiring link to the interview panel/CEO role, without exposing raw transcript unless explicitly enabled by the recruiter.

### M9-F05 — Reviewer Feedback Loop

Recruiter/panel can attach a final human decision and comment to the report; discrepancies between AI verdict and human decision feed the calibration dataset (M6-F04) to continuously improve future prompt/scoring versions.

---

## M10 — Dashboards

### M10-F01 — HR Dashboard

Active assessments, candidates in progress, completed interviews awaiting review, pending final decisions, and quick links into each report.

### M10-F02 — Candidate Dashboard

Invitation status, interview instructions and modality, time remaining to complete, and post-completion status (no internal scores exposed).

### M10-F03 — Admin Dashboard

Org users/roles, competency library management, department/role templates, billing/plan status.

### M10-F04 — Reports Dashboard

Searchable/filterable archive of all completed hiring reports across roles and departments, with verdict and score-band filters.

---

## M11 — Analytics

### M11-F01 — Score Trends

Average scores over time, department-wise, skill-wise, and role-wise.

### M11-F02 — Hiring Funnel Analytics

Conversion rate from invited → completed → hired at each stage, by department and role.

### M11-F03 — Question & Difficulty Analytics

Distribution of question categories generated, average difficulty mix per assessment, and correlation between category coverage and eventual verdict — used to tune M4's category weighting over time.

### M11-F04 — Candidate Benchmarking

Percentile ranking of a candidate's scores against all other candidates assessed for the same role/level within the org.

### M11-F05 — Skill Trend & Hiring Prediction

Surfaces top and weakest skill trends across completed assessments, and (as a v2+ capability, see §17) a predictive signal for likely on-the-job success based on historical hire outcomes where available.

---

## M12 — Platform Administration

### M12-F01 — Tenant & Workspace Management

Super Admin provisions org workspaces, manages plan tiers, and monitors per-tenant usage.

### M12-F02 — Prompt Library Management

Central, versioned repository of every agent's prompt templates (§7 Prompt Templates), with rollout/rollback controls per tenant or globally.

### M12-F03 — Model Routing Configuration

Configures which LLM/model powers each agent (resume parsing vs. upfront question generation vs. report writing may reasonably use different models/latency tiers), with fallback routing on provider outage.

### M12-F04 — System Health & Incident Monitoring

Queue depth, generation latency (p50/p95/p99), agent error rates, and fraud-flag false-positive tracking dashboard.

---

## 7. AI Agent Architecture

ARAP is implemented as a **multi-agent system** where each agent has one clear responsibility and communicates through structured JSON handoffs, not free-form chat history, so any agent can be swapped, versioned, or re-prompted independently.

| Agent | Responsibility | Primary Inputs | Primary Output |
|---|---|---|---|
| **Resume Analysis Agent** | Parses resume/LinkedIn/GitHub/portfolio into structured candidate data | Raw resume file/URLs | `candidate_profile` JSON (M2, M3) |
| **Job Description Agent** | Normalizes the job assessment into a structured competency/skill graph used by all downstream agents | `job_assessment` (M1) | `job_profile` JSON, competency weightage map |
| **Question Generation Agent** | Generates the full personalized question set upfront, in one batch, before the test is sent | `job_profile`, `candidate_profile`, category weightage, risk flags | Complete `question_set` JSON (M4) |
| **Evaluation Agent** | Scores every submitted answer against the rubric after the candidate submits | `question_set`, `submitted_answers`, relevant rubric slices | Per-competency scores + explanation + evidence citation (M6) |
| **Behavior Analysis Agent** | Infers personality/leadership/EQ signals from the full submitted answer set | Full set of submitted answers | DISC, Big Five, leadership/decision/communication style, EQ signal (M7) |
| **Scoring Agent** | Rolls up per-answer scores into session-level and report-level scores | All per-answer evaluations, job weightage | Session score roll-up (M6-F03) |
| **Recommendation Agent** | Synthesizes scores + behavior + fraud signals into salary band, verdict, and training needs | Scoring Agent output, Behavior Analysis output, Fraud output | Recommendation block for report (M9) |
| **Report Generator Agent** | Composes the final structured, human-readable hiring report | All above agent outputs | Final report document (M9) |

An implicit **Fraud/Integrity function** (M8) runs as a set of deterministic + embedding-similarity checks alongside the Evaluation Agent rather than as a separate conversational agent, since its checks are largely statistical, not generative.

Agents communicate via a shared **session state object**, so any agent invocation is stateless and idempotent given that state — critical for retries and for auditability of exactly what context produced a given question or score.

### Prompt Template Pattern (representative — Question Generation Agent)

```
SYSTEM:
You are the Question Generation Agent for a personalized recruitment
assessment. Generate the COMPLETE question set for this candidate in one
pass. Never repeat or closely paraphrase any question already generated
for this org's question-fingerprint history. Match the category weightage
and difficulty level supplied.

CONTEXT:
job_profile: {job_profile_json}
candidate_profile: {candidate_profile_json}
category_weightage: {category_weightage_json}
difficulty_level: {difficulty_level}
risk_flags: {risk_flags_json}
target_question_count: {question_count}

OUTPUT (JSON only):
{
  "questions": [
    {
      "question": string,
      "category": string,
      "target_competencies": string[],
      "difficulty": "easy"|"medium"|"hard"|"expert",
      "answer_format": "multiple_choice"|"short_text"|"long_text",
      "options": string[]  // present only when answer_format is multiple_choice
    }
  ]
}
```

Equivalent structured templates exist for the Evaluation, Behavior Analysis, Recommendation, and Report Generator agents, each with a fixed JSON output contract so the pipeline never depends on free-text parsing.

---

## 8. Question Generation & Test Flow

1. **Job assessment created** (M1) — recruiter defines role, skills, competency weightage, difficulty level, duration.
2. **Resume ingested and parsed** (M2), **candidate profile synthesized** (M3) — skills, strengths, risk flags.
3. **Generate full question set** in a single batch via the Question Generation Agent (§7), scoped to: the job profile, the candidate profile, the category weightage map (M1-F02/M4-F02), and any risk flags to target (M4-F04) — constrained by the no-repeat fingerprint check (M4-F05).
4. **Lock the set** against the `assessment_session` (M4-F06) and **send the test link by email** to the candidate.
5. **Candidate logs in** (passwordless, session-scoped, §4.1) and **starts the test** — the locked question set is shown, DISC-style, one question at a time or paginated (M5-F02).
6. **Candidate answers and submits** the full set, within the configured time window (M5-F04).
7. **On submission**, trigger in sequence: Evaluation Agent batch scoring (M6-F01/F02) → Behavior Analysis Agent (M7) → Fraud checks (M8) → Scoring Agent roll-up (M6-F03) → Recommendation Agent → Report Generator Agent (M9).
8. **Report becomes available** to the recruiter/admin (M10) within the target turnaround (§3).

There is no live, turn-by-turn interaction between the candidate and the AI during the test — all AI work happens either before the test is sent (question generation) or after it is submitted (evaluation, behavior inference, fraud checks, report generation).

---

## 9. Scoring & Evaluation Framework

### 9.1 Competency Set (scored per answer, only where relevant to the question)

Technical Accuracy · Depth of Knowledge · Confidence · Leadership · Communication · Logical Thinking · Critical Thinking · Business Thinking · Problem Solving · Decision Making · Innovation · Risk Awareness · Ownership · Teamwork · Conflict Handling · Customer Focus · Learning Ability · Adaptability · Culture Fit · Professionalism

### 9.2 Scoring Scale

Each competency is scored 1–5 per relevant answer (1 = major gap, 3 = meets bar, 5 = exceptional), with a mandatory text explanation and a quoted evidence excerpt (M6-F02). Raw scores are never shown to the candidate — only to recruiter/panel roles.

### 9.3 Roll-Up Formula

Session-level competency score = weighted average of all per-answer scores for that competency, weighted by (a) the job assessment's competency weightage (M1-F01) and (b) question difficulty (harder questions answered well weigh more than easy questions answered well).

Report-level composite scores (Technical, Leadership, Communication, Behavior, Culture Fit) are weighted roll-ups of their constituent competencies, using the same job-assessment weightage so the composite always reflects what *this specific role* actually values.

### 9.4 AI Confidence Score

A separate meta-score (0–100%) reflecting the Report Generator Agent's own confidence in the verdict, driven by: resume parsing confidence (M2-F02), interview completion percentage, evidence density (number of distinct answers backing each composite score), and absence/presence of fraud flags (M8). Low-confidence reports are visually flagged in M9/M10 and should route to a mandatory human review rather than an automated pass-through.

### 9.5 Verdict Bands

| Composite Score Band | Verdict |
|---|---|
| ≥ 90% and no High-severity integrity flag | Strong Hire |
| 75–89% | Hire |
| 60–74% | Consider |
| 45–59% | Borderline |
| < 45%, or any High-severity integrity flag | Reject |

Bands are configurable per org (M12) but ship with the above default.

---

## 10. Non-Functional Requirements

### Performance
Non-generative API endpoints: p95 < 400ms. Question-set generation (upfront, per candidate): p95 < 6s per question, run asynchronously before the invite email is sent. Report generation: complete within 5 minutes of test submission (§3).

### Reliability
99.5% monthly uptime target. Interview sessions must survive a candidate's transient disconnect/reconnect without losing session state (session state is persisted after every turn, per §7).

### Usability
Candidate-facing interview UI must work on standard broadband and degrade gracefully to text-only if voice/video fails mid-session, without losing scoring continuity.

### Security
See §15 in full. Summary: tenant data isolation at DB and API layer; resumes and interview recordings encrypted at rest; role-based access strictly enforced per §4.2.

### Observability
Full request tracing per agent call (model, prompt version, latency, token cost) for cost monitoring and prompt-regression detection; every generated question and score traceable to the exact prompt version that produced it.

### Accessibility
Candidate test UI meets WCAG 2.1 AA.

---

## 11. Technical Architecture

### 11.1 Technology Stack

**Frontend:** React, Next.js, TypeScript, Tailwind CSS — separate app shells for the Candidate interview runtime (minimal, low-distraction UI) and the HR/Admin/Analytics console (dense, data-rich UI).

**Backend:** Python FastAPI for all AI-orchestration and agent-invocation services; Node.js for real-time session/session-state/WebRTC signaling services where lower-latency event handling is beneficial.

**AI Layer:** LLM provider(s) configurable per agent via Model Routing (M12-F03) — e.g., Claude/GPT-class models for generative agents (question generation, report writing), a smaller/faster model tier for deterministic scoring sub-tasks where latency matters more than nuance. Embedding model for resume-to-JD matching (M2-F04), no-repeat question fingerprinting (M4-F05), and duplicate-answer fraud detection (M8-F02).

**Data:** PostgreSQL as system of record; `pgvector` extension for embedding storage/similarity search (no separate vector DB required at MVP scale — revisit in §17 if corpus size demands it); Redis for session state caching and real-time interview turn coordination.

**Speech/Video:** Speech-to-Text and Text-to-Speech services for voice mode (M5-F02); WebRTC for video capture/signaling (M5-F03).

**Infra:** Docker containers; AWS hosting (ECS/Fargate or equivalent); S3-compatible object storage for resumes, audio, and video artifacts (encrypted at rest, §15).

**Auth:** JWT-based authentication, RBAC per §4.2.

### 11.2 Repository Structure (proposed)

```
arap/
  apps/
    candidate-web/        # Next.js candidate interview runtime
    console-web/          # Next.js HR/Admin/Analytics console
  services/
    orchestrator-api/     # FastAPI — agent orchestration, session state
    realtime-gateway/     # Node.js — WebRTC signaling, live turn coordination
    ingestion-service/    # Resume/LinkedIn/GitHub parsing pipeline
  agents/
    resume_analysis/
    job_description/
    question_generation/
    evaluation/
    behavior_analysis/
    scoring/
    recommendation/
    report_generator/
  packages/
    prompt-library/       # Versioned prompt templates (M12-F02)
    shared-types/         # Shared TS/Pydantic schema contracts between agents
  infra/
    docker/
    terraform/ (or equivalent IaC)
```

### 11.3 High-Level AI Workflow

```
Job Assessment (M1) ──┐
                       ├─→ Job Description Agent ──→ job_profile
Resume Upload (M2) ────┘

job_profile + Resume Analysis Agent ──→ candidate_profile (M3)

[Upfront Question Generation — §8]
job_profile + candidate_profile
  ──→ Question Generation Agent ──→ question_set (locked, M4-F06)
  ──→ email test link ──→ Test Delivery (M5)

candidate submits full answer set (M5)
  ──→ Evaluation Agent ──→ per-answer scores (M6)
  ──→ Behavior Analysis Agent ──→ behavior_profile (M7)
  ──→ Fraud checks (M8) ──→ integrity_summary
all above ──→ Scoring Agent ──→ score_rollup
score_rollup + behavior_profile + integrity_summary
  ──→ Recommendation Agent ──→ recommendation_block
recommendation_block ──→ Report Generator Agent ──→ final_report (M9)
```

---

## 12. Data Model

### `orgs`
`id, name, plan_tier, created_at`

### `users`
`id, org_id, email, role (user|admin), created_at`

### `job_assessments` (M1)
`id, org_id, title, department, experience_min, experience_max, required_skills[], preferred_skills[], responsibilities, education, certifications[], behavioral_competencies[], leadership_competencies[], culture_values[], difficulty_level, duration_minutes, competency_weightage (jsonb), created_by, created_at`

### `candidates`
`id, org_id, name, email, resume_file_url, linkedin_url, github_url, portfolio_url, auth_method (magic_link|otp|password), password_hash (nullable), login_token_hash (nullable), login_token_expires_at (nullable), last_login_at (nullable), created_at`

### `clients`
`id, org_id, name, email, auth_method (magic_link|otp|password), password_hash (nullable), login_token_hash (nullable), login_token_expires_at (nullable), last_login_at (nullable), created_at`

### `report_shares` (Client access scoping)
`id, hiring_report_id, client_id, shared_by (user_id), expires_at (nullable), revoked_at (nullable), created_at`

### `candidate_profiles` (M3)
`id, candidate_id, job_assessment_id, summary, skill_matrix (jsonb), experience_matrix (jsonb), leadership_level_estimate, strengths[], risk_flags[], parsing_confidence, created_at`

### `assessment_sessions` (M4/M5)
`id, job_assessment_id, candidate_id, candidate_profile_id, status (invited|in_progress|completed|expired), invited_at, started_at, completed_at, time_budget_seconds`

### `question_sets` (M4)
`id, session_id, generated_at, locked_at, generation_prompt_version`

### `session_questions` (M4/M5/M6)
`id, question_set_id, sequence_no, question (jsonb), category, target_competencies[], difficulty, answer_format (multiple_choice|short_text|long_text), options (jsonb, nullable), answer_text, answered_at, evaluation (jsonb — per-competency scores + explanation + evidence excerpt), created_at`

### `question_fingerprints` (M4-F05)
`id, org_id, question_embedding (vector), question_text, question_set_id, created_at`

### `behavior_profiles` (M7)
`id, session_id, disc_style (jsonb), big_five (jsonb), leadership_style, decision_style, communication_style, work_style, stress_signal, eq_signal, team_compatibility_signal, created_at`

### `integrity_flags` (M8)
`id, session_id, session_question_id (nullable), flag_type (ai_generated|duplicate_answer|resume_inconsistency|behavioral_anomaly), severity (low|medium|high), evidence, created_at`

### `hiring_reports` (M9)
`id, session_id, executive_summary, score_rollup (jsonb), behavior_profile_id, integrity_summary (jsonb), salary_band, verdict, ai_confidence_score, recommended_next_round, training_needs[], suggested_hr_questions[], suggested_ceo_questions[], reviewer_override (jsonb, nullable), created_at`

### `competency_library` (M1-F02)
`id, org_id, name, description, rubric_notes, created_by`

### `prompt_templates` (M12-F02)
`id, agent_name, version, template_body, is_active, created_at`

### `audit_logs`
`id, org_id, actor_id, action, entity_type, entity_id, metadata (jsonb), created_at`

---

## 13. REST API Design

Representative endpoints (full OpenAPI spec to be generated from FastAPI implementation):

```
POST   /api/v1/job-assessments                     Create job assessment (M1)
GET    /api/v1/job-assessments/{id}                 Fetch job assessment
POST   /api/v1/job-assessments/{id}/clone           Clone as template (M1-F03)

POST   /api/v1/candidates                           Register candidate
POST   /api/v1/candidates/{id}/resume                Upload resume (M2)
GET    /api/v1/candidates/{id}/profile               Fetch candidate_profile (M3)

POST   /api/v1/auth/candidate/request-login          Request magic link/OTP for invited email (M1-F04)
POST   /api/v1/auth/candidate/verify                 Verify token/OTP, issue session-scoped JWT
POST   /api/v1/auth/client/request-login              Request magic link/OTP for shared-report email (M9-F04)
POST   /api/v1/auth/client/verify                     Verify token/OTP, issue report-scoped JWT

POST   /api/v1/sessions                              Create assessment_session (M1-F04)
POST   /api/v1/sessions/{id}/generate-questions       Generate + lock question_set, send test-link email (M4)
GET    /api/v1/sessions/{id}                         Session status/state (candidate JWT required)
GET    /api/v1/sessions/{id}/questions                Fetch locked question set for the test UI (candidate JWT required)
POST   /api/v1/sessions/{id}/answers                  Submit full answer set (candidate JWT required)
POST   /api/v1/sessions/{id}/complete                Finalize session, trigger evaluation pipeline (§11.3)

GET    /api/v1/sessions/{id}/report                  Fetch hiring_report (M9)
POST   /api/v1/sessions/{id}/report/override          Recruiter override/annotation (M6-F04, M9-F05)
GET    /api/v1/sessions/{id}/report/export            PDF export (M9-F04)
GET    /api/v1/reports/shared/{report_share_id}       Client-facing scoped report view (client JWT required)

GET    /api/v1/analytics/score-trends                 M11-F01
GET    /api/v1/analytics/hiring-funnel                M11-F02
GET    /api/v1/analytics/question-analytics           M11-F03
GET    /api/v1/analytics/candidate-benchmark/{id}     M11-F04

GET    /api/v1/admin/competency-library               M1-F02
POST   /api/v1/admin/prompt-templates                 M12-F02 (admin only)
PUT    /api/v1/admin/model-routing                    M12-F03 (admin only)
```

All endpoints require a JWT bearer token; every request is scoped to `org_id` from the token claims except `admin`-only routes under `/api/v1/admin/*` explicitly marked cross-tenant. Candidate and Client JWTs carry an additional scope claim (`assessment_session_id` or `report_share_id` respectively) that further restricts them to a single resource, independent of the `org_id` scoping applied to Admin/User tokens.

---

## 14. Key User Flows

### 14.1 End-to-End Assessment Flow
Recruiter creates job assessment (M1) → uploads/links the candidate's resume (M2) → candidate profile synthesized (M3) → Question Generation Agent generates and locks the full personalized question set (M4) → system emails the candidate a scoped test link (M5-F01) → candidate opens the link, logs in via passwordless magic link/OTP (§4.1) → candidate takes the test DISC-style (M5-F02) and submits → Evaluation Agent scores the full answer set, then Behavior Analysis + Fraud checks + Scoring + Recommendation run in sequence (§11.3) → Report Generator produces final report (M9) → recruiter reviews, optionally overrides, shares with panel/CEO (M9-F04/F05) → Client/panel recipient logs in via the same passwordless mechanism to view only the shared report → final human decision recorded, fed back into calibration (M6-F04).

### 14.2 Question Generation & Test-Taking Cycle
Job assessment + candidate profile ready → Question Generation Agent produces the complete question set in one pass, checked against the no-repeat fingerprint (M4-F05) → set is locked to the session (M4-F06) → test link emailed → candidate logs in, answers questions at their own pace, saved incrementally (M5-F05) → candidate submits the full set → Evaluation Agent scores every answer in a single batch pass (M6-F01).

### 14.3 Fraud Flag Review
Integrity flag raised mid-session or at finalization (M8) → surfaced in Report's Integrity Summary with severity and evidence (M8-F05) → recruiter reviews evidence directly (transcript excerpt, similarity match, or audio segment) → recruiter marks flag as dismissed or confirmed → confirmed flags factor into final verdict override.

### 14.4 Report Escalation to CEO Round
Recruiter reviews completed report → shares scoped read-only link with Panel/CEO role (M9-F04) → CEO reviewer sees AI-suggested CEO-round questions (M9-F02) generated specifically to probe remaining risk areas → CEO records final round outcome, appended to the same report record.

---

## 15. Security, Privacy & Compliance

- **Tenant isolation:** every table carries `org_id`; all queries are scoped at the ORM/service layer, enforced additionally by row-level security in PostgreSQL.
- **PII handling:** resumes, transcripts, and audio/video recordings are personal data — encrypted at rest (S3 SSE) and in transit (TLS 1.2+); access logged in `audit_logs`.
- **Candidate consent:** candidates must explicitly consent to AI-based evaluation, recording, and behavioral inference before a session starts; consent timestamp and version stored against the session. Consent capture happens after login (§4.1) and before the interview begins.
- **Candidate/Client credentials:** both authenticate via passwordless login (magic link or OTP sent to the invited/shared email) by default, avoiding stored passwords for non-workspace identities; login tokens are single-use, short-lived, and scoped to exactly one `assessment_session` (Candidate) or one `report_share` record (Client) — never a general-purpose account session.
- **No biometric identity inference:** video/audio signals are used only for engagement/integrity flags (M8-F04) and never for facial recognition, emotion-as-hiring-criterion, or any characteristic protected under applicable anti-discrimination law (age, gender, ethnicity, disability) — this must be explicitly excluded from all agent prompts and validated in testing.
- **Explainability requirement:** every score in a report must be traceable to a transcript excerpt (M6-F02) so a rejected candidate's outcome can be explained and defended if challenged — a legal as well as product requirement in most jurisdictions with algorithmic-hiring disclosure rules.
- **Human-in-the-loop mandate:** the AI never issues a final hiring decision autonomously; M9's "Final Verdict" is a recommendation requiring recruiter/panel confirmation (M9-F05), and low-AI-confidence reports (§9.4) route to mandatory human review.
- **Data retention:** candidate resumes/recordings/transcripts retained per org-configurable policy (default: 12 months post-decision) with a deletion workflow for right-to-erasure requests.
- **RBAC:** enforced per §4.2; JWT with short-lived access tokens + refresh tokens.
- **Penetration testing:** required before commercial launch, zero critical/high findings (aligned to §3 goal).

---

## 16. Development Phases

**Phase 0 — Foundation (Weeks 1–3)**
Auth/RBAC, org/tenant scaffolding, Job Assessment Builder (M1), basic resume upload/parsing (M2-F01/F02).

**Phase 1 — MVP: Question Generation & Test Delivery (Weeks 4–8)**
Candidate Profile Engine (M3), Question Generation Engine (M4), Test Delivery (M5) with emailed test link and DISC-style runtime, Evaluation Engine (M6), basic Hiring Report (M9-F01/F02) without behavior inference or fraud detection. HR + Candidate dashboards (M10-F01/F02).

**Phase 2 — Behavioral Intelligence & Integrity (Weeks 9–13)**
Behavior Inference Engine (M7), Fraud & Integrity Detection (M8), report enrichment with Integrity Summary and behavioral profile, reviewer feedback/calibration loop (M6-F04, M9-F05).

**Phase 3 — Extended Answer Formats (Weeks 14–18)**
Multiple-choice, short-text, and long-text answer formats fully supported in the test runtime; richer question-set review UI for recruiters.

**Phase 4 — Structured Assessment Extensions (Weeks 19–22)**
Coding-question support with sandboxed auto-grading, case-study/presentation-style questions — extending the static test format rather than reintroducing live delivery (see §17 for deferred voice/video/live-interview modalities).

**Phase 5 — Analytics & Scale (Weeks 23–26)**
Full Analytics module (M11), Admin/Reports dashboards (M10-F03/F04), competency library and templates (M1-F02/F03), model routing configuration (M12-F03).

**Phase 6 — Hardening & Commercial Launch**
Penetration testing, load testing to target concurrency, calibration validation against a labeled candidate set (§3 inter-rater agreement target), documentation, and design-partner rollout.

---

## 17. Future Enhancements

- Predictive on-the-job success modeling once sufficient historical hire-outcome data exists (M11-F05 v2).
- Dedicated vector database migration if `pgvector` similarity search latency becomes a bottleneck at scale.
- Multi-language test support (resume + question set) for non-English-first markets.
- Voice/video answer formats and a live, real-time AI-interviewer mode (turn-by-turn adaptive questioning) as an optional alternative to the static test format, for roles where a synchronous conversational assessment is preferred.
- Panel-of-AI-agents debate mode for borderline verdicts (a second independent Recommendation Agent pass to check for reasoning drift).
- Continuous learning loop: automatic prompt-version A/B testing against calibration data (§6-F04) with statistical significance gating before promoting a new prompt version org-wide.
- Candidate-side practice/prep mode (non-scored) to reduce first-time-format anxiety, kept clearly separate from any scored assessment.
- Integration connectors to common ATS platforms (Greenhouse, Lever, Workday) for invite trigger and report push-back.

---

## 18. Open Questions & Assumptions

1. **Salary recommendation data source** — the salary-band section of the report (M9-F02) requires a market-compensation data input (internal comp bands vs. a third-party salary API). Not yet decided; assumed org-provided comp bands at MVP, external API integration deferred to Phase 5+.
2. **Video/emotion analysis scope** — §15 explicitly excludes biometric/emotion-based scoring; confirm this restriction against any jurisdiction-specific algorithmic hiring regulations before Phase 3 video work begins.
3. **LLM provider selection per agent** — §11.1/M12-F03 assumes multi-model routing; specific provider/model choice per agent to be finalized against cost and latency benchmarking in Phase 1.
4. **Fraud detection false-positive tolerance** — §3 target (recall >85%, false-positive <10%) assumes a labeled validation dataset will be constructed; sourcing/labeling this set is a Phase 2 prerequisite, not yet scoped.
5. **Human calibration set size** — §3's inter-rater agreement target (>75%) requires an initial set of AI-vs-human-reviewed sessions; volume and sourcing (pilot org volunteers vs. synthetic) to be decided before Phase 6 validation.
6. **ATS integration priority** — §17 lists ATS connectors as future work; no specific ATS has been confirmed as a Phase 1 requirement — assumed standalone platform at MVP.

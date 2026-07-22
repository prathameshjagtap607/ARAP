# ==============================================================================
# arap-sessions.ps1
# ARAP -- AI Recruitment Assessment Platform -- Claude Code Session Launcher
# Owner: Srinivas / Fidelitus Corp
# PRD: v1.0, 20 July 2026
# Usage: .\arap-sessions.ps1 -Session <name>
#        .\arap-sessions.ps1 -Session list
# ==============================================================================

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet(
        "schema","scaffold","auth",
        "job-assessment","resume-ingestion","candidate-profile",
        "question-gen","test-delivery","evaluation",
        "behavior-inference","fraud-integrity","hiring-report",
        "dashboards","analytics","admin",
        "frontend-candidate","frontend-console",
        "debug","list"
    )]
    [string]$Session
)

$PROJECT_ROOT = "D:\staging\ARAP1"
$HAIKU        = "claude-haiku-4-5-20251001"
$SONNET       = "claude-sonnet-4-6"

# -- SESSION DEFINITIONS -------------------------------------------------------
$sessions = @{

    # -- Phase 0 . Foundation --------------------------------------------------
    schema = @{
        model = $SONNET
        task  = "TASK-000"
        label = "Phase 0 . Data Model (Postgres/pgvector) [COMPLETE]"
        prompt = @'
*** SESSION COMPLETE — DO NOT RE-RUN ***
All 17 models, Alembic migration, RLS policies, HNSW index, and 44 tests are
done. Final commit: f1ac4e2 on main (pushed to origin).
Progress ledger: .superpowers/sdd/progress.md

Next session: .\arap-sessions.ps1 -Session scaffold
'@
    }

    scaffold = @{
        model = $SONNET
        task  = "TASK-000"
        label = "Phase 0 . Repo Scaffold & Shell [COMPLETE]"
        prompt = @'
*** SESSION COMPLETE — DO NOT RE-RUN ***
Full monorepo layout, FastAPI bootstrap, Next.js shells, CI, docker-compose done.
46 tests passing. Final commit: 668328c on main.

What was built:
  - apps/candidate-web (port 3000) + apps/console-web (port 3002) — both boot ✓
  - services/orchestrator-api: GET /health working, middleware stubs ready for auth
  - services/realtime-gateway, services/ingestion-service: health stubs
  - agents/: 8 skeleton folders
  - packages/shared-types, packages/prompt-library
  - root docker-compose.yml (.env.example), .github/workflows/ci.yml
Progress ledger: .superpowers/sdd/progress.md (all 12 tasks logged)

Next session: .\arap-sessions.ps1 -Session auth
'@
    }

    auth = @{
        model = $SONNET
        task  = "TASK-000"
        label = "Phase 0 . Auth, RBAC & Passwordless Login"
        prompt = @'
Stack: FastAPI, PostgreSQL, JWT (access+refresh), Redis (token/session store)
Task file: tasks/TASK-000-phase0-foundation.md
Module scope: services/orchestrator-api/src/modules/auth ONLY.

Objective: Auth + RBAC per PRD Section 4 and Section 15.
  4 identities: Admin, User (password login), Candidate, Client (both passwordless)
  Admin/User: JWT access (short-lived) + refresh token; bcrypt password hashing
  Candidate/Client: magic-link or OTP to invited/shared email; login tokens are
    single-use, short-lived, and scoped to exactly ONE assessment_session
    (Candidate) or ONE report_share record (Client) -- never a general account
  Candidate JWT carries assessment_session_id scope claim; Client JWT carries
    report_share_id scope claim -- enforced on every request, not just org_id
  RBAC matrix enforced SERVER-SIDE per Section 4.2 access control matrix
  Tenant isolation: every query scoped to org_id except Admin cross-tenant routes
  All auth events + mutations written to audit_logs

role and scope claims extracted from JWT payload -- never from request body.

Exit criteria: all 4 login flows working; session/report scoping verified
  (a candidate JWT cannot fetch any session other than its own).
Context7: use for FastAPI security/OAuth2, PyJWT, passlib/bcrypt.
PDCA: present plan before touching any file.
'@
    }

    # -- Phase 1 . MVP: Question Gen & Test Delivery ---------------------------
    "job-assessment" = @{
        model = $SONNET
        task  = "TASK-001"
        label = "Phase 1 . Job Assessment Builder (M1)"
        prompt = @'
Stack: FastAPI, PostgreSQL, Next.js (console-web)
Task file: tasks/TASK-001-phase1-question-test.md
Module scope: services/orchestrator-api/src/modules/job_assessments +
  agents/job_description ONLY.

Objective: Job Assessment Builder per PRD M1 (F01-F04).
  Job Assessment Creation (M1-F01): company, department, title, experience
    min/max, required/preferred skills, responsibilities, education, certs,
    behavioral + leadership competencies, culture values, difficulty level
    (Junior/Mid/Senior/Executive), duration, per-competency weightage
    (MUST sum to 100% -- validate server-side)
  Competency Library (M1-F02): org-scoped reusable competency definitions
    with rubric description; custom one-off competencies still allowed
  Templates & Cloning (M1-F03): save assessment as reusable template per
    role family, clone with adjustable weightage/skills
  Candidate Invitation (M1-F04): invite creates a distinct assessment_session
    scoped 1:1:1 to one candidate, one job_assessment, one resume upload

Job Description Agent (§7): normalizes job_assessment into job_profile JSON +
  competency weightage map -- this is the grounding context for every
  downstream agent (question gen, evaluation, report benchmarking).

Exit criteria: assessment CRUD + templates + weightage validation working;
  job_profile JSON produced and stored.
Context7: use for FastAPI + Pydantic validation, Next.js forms.
PDCA: present plan before touching any file.
'@
    }

    "resume-ingestion" = @{
        model = $SONNET
        task  = "TASK-001"
        label = "Phase 1 . Resume & Profile Ingestion (M2)"
        prompt = @'
Stack: FastAPI, PostgreSQL, S3-compatible storage, embedding model
Task file: tasks/TASK-001-phase1-question-test.md
Module scope: services/ingestion-service + agents/resume_analysis ONLY.

Objective: Resume & Profile Ingestion per PRD M2 (F01-F04).
  Multi-Format Upload (M2-F01): PDF/DOCX/plain text, LinkedIn URL, GitHub
    handle/URL, portfolio URL; parse synchronously (<10s target) with a
    job-queue fallback for larger docs
  Resume Parsing Extraction (M2-F02): Resume Analysis Agent extracts skills
    (explicit/inferred), projects, tech used, employment history, education,
    certifications, quantified achievements, leadership indicators (team
    size/scope), career timeline (gaps + length/count), domain keywords, and
    a PER-FIELD parsing confidence score
  GitHub/Portfolio Enrichment (M2-F03): pull public repo metadata (languages,
    commit recency, README quality, pinned projects) + portfolio case studies
    -- additive evidence only, never a hard gate
  Resume-to-JD Match Score (M2-F04): embeddings-based semantic match between
    parsed resume and job_assessment required/preferred skills

Output contract: candidate_profile JSON (feeds M3).

Exit criteria: parsing confidence scores populated; match score computed and
  surfaced before interview scheduling.
Context7: use for resume-parsing libraries, embedding API, S3 signed URLs.
PDCA: present plan before touching any file.
'@
    }

    "candidate-profile" = @{
        model = $SONNET
        task  = "TASK-001"
        label = "Phase 1 . Candidate Profile Engine (M3)"
        prompt = @'
Stack: FastAPI, PostgreSQL
Task file: tasks/TASK-001-phase1-question-test.md
Module scope: services/orchestrator-api/src/modules/candidate_profiles ONLY.

Objective: Candidate Profile Engine per PRD M3 (F01-F04).
  Candidate Summary Generation (M3-F01): 2-3 paragraph narrative -- current
    role, trajectory, standout achievements, domain fit -- generated jointly
    by Job Description Agent + Resume Analysis Agent against the specific
    job_assessment
  Skill & Experience Matrix (M3-F02): required/preferred skill -> evidence
    (yes/partial/no), estimated years applied, confidence
  Career Growth & Leadership Estimate (M3-F03): career velocity, current
    leadership level (IC/Team Lead/Manager/Director/VP-equiv), scope (team
    size, budget, geography) -- from resume signal, refined later by interview
  Strength/Risk Flagging (M3-F04): flags that seed targeted M4 questions
    (e.g. "no direct people-management despite Manager title", resume gaps)

Persist to candidate_profiles table (summary, skill_matrix jsonb,
  experience_matrix jsonb, leadership_level_estimate, strengths[], risk_flags[]).

Exit criteria: profile synthesized end-to-end from a real parsed resume;
  risk_flags feed M4 question seeding.
Context7: use for FastAPI + Pydantic, LLM structured-output patterns.
PDCA: present plan before touching any file.
'@
    }

    "question-gen" = @{
        model = $SONNET
        task  = "TASK-001"
        label = "Phase 1 . Question Generation Engine (M4)"
        prompt = @'
Stack: FastAPI, PostgreSQL + pgvector, LLM API (per M12-F03 routing), embeddings
Task file: tasks/TASK-001-phase1-question-test.md
Module scope: agents/question_generation +
  services/orchestrator-api/src/modules/question_sets ONLY.

Objective: Question Generation Engine per PRD M4 (F01-F06) and the prompt
  template in PRD Section 7.
  Upfront Generation (M4-F01): full question set for the candidate in ONE
    batch call, from job_profile + candidate_profile + category weightage --
    NO live regeneration or difficulty adaptation during the test
  Category Coverage (M4-F02): balanced coverage across the 21 categories
    (Technical, Behavioral, Leadership, Case Study, Scenario, Decision-Making,
    Conflict Resolution, Problem Solving, Analytical, Situational Judgment,
    Communication, Ethics, Innovation, Culture Fit, Stress, Priority
    Management, Negotiation, Business Strategy, Financial, Presentation,
    Customer Handling), weighted by job_assessment competency weightage
  Resume-Referenced Questions (M4-F03): at least one question must directly
    cite the candidate's resume
  Risk-Flag Targeted Questions (M4-F04): M3 risk flags seed specific questions
  No-Repeat Guarantee (M4-F05): embed every generated question, reject/
    regenerate anything above similarity threshold vs. question_fingerprints
    (org-scoped, pgvector similarity search)
  Set Finalization & Lock (M4-F06): once sent, question_set is immutable for
    that assessment_session

Use the exact JSON output contract from PRD Section 7 (Prompt Template
  Pattern) -- questions[] with question/category/target_competencies/
  difficulty/answer_format/options.

Exit criteria: two sessions for the same role/different candidates produce
  0% verbatim question overlap (PRD Section 3 goal); p95 < 6s per question.
Context7: use for LLM structured JSON output, pgvector similarity queries.
PDCA: present plan before touching any file -- this is the highest-risk
  generative component, confirm approach before implementing.
'@
    }

    "test-delivery" = @{
        model = $SONNET
        task  = "TASK-001"
        label = "Phase 1 . Test Delivery Runtime (M5)"
        prompt = @'
Stack: Next.js (candidate-web), FastAPI, Redis (session state), email provider
Task file: tasks/TASK-001-phase1-question-test.md
Module scope: apps/candidate-web/src + services/orchestrator-api/src/modules/sessions ONLY.

Objective: Test Delivery per PRD M5 (F01-F05).
  Emailed Test Link (M5-F01): once question_set is generated+locked, email a
    scoped link tied to assessment_session; clicking starts passwordless login
  DISC-Style Runtime (M5-F02): static, self-paced Q&A -- one at a time or
    paginated; candidate can navigate between questions before final submit;
    NO live AI interaction, no adaptive branching
  Answer Formats (M5-F03): multiple_choice, short_text, long_text (voice/
    video/coding sandbox are OUT OF SCOPE, deferred per PRD Section 17)
  Time-Bound Window (M5-F04): enforce job_assessment.duration_minutes as an
    overall timer; auto-submit whatever is answered at expiry
  Save & Resume (M5-F05): persist progress after EVERY answered question so
    a transient disconnect never loses already-submitted answers

Candidate-facing UI: minimal, low-distraction, WCAG 2.1 AA (PRD Section 10).

Exit criteria: full test flow (login -> answer -> autosave -> timer -> submit)
  survives a simulated disconnect/reconnect without data loss.
Context7: use for Next.js forms/state, FastAPI WebSocket or polling patterns.
PDCA: present plan before touching any file.
'@
    }

    evaluation = @{
        model = $SONNET
        task  = "TASK-001"
        label = "Phase 1 . Evaluation Engine (M6) + Basic Report (M9-F01/F02)"
        prompt = @'
Stack: FastAPI, PostgreSQL, LLM API
Task file: tasks/TASK-001-phase1-question-test.md
Module scope: agents/evaluation + agents/scoring +
  services/orchestrator-api/src/modules/reports (basic only) ONLY.

Objective: Evaluation Engine per PRD M6 (F01-F04) + Section 9 scoring
  framework, plus a BASIC hiring report (M9-F01/F02 only -- no behavior
  inference or fraud detection yet, those are Phase 2).
  Batch Scoring (M6-F01): after full-set submission, score every answer
    against the 20-competency rubric (Section 9.1), but ONLY the competencies
    relevant to that question's category -- never all 20 per answer
  Explanation & Evidence (M6-F02): every score has a text explanation +
    quoted excerpt from the candidate's own answer, one explicit strength,
    one explicit improvement area
  Session Roll-Up (M6-F03): weighted average per competency using job
    weightage (a) and question difficulty (b) per Section 9.3 formula ->
    Technical/Leadership/Communication/Behavior composite scores
  Calibration (M6-F04): recruiter can override any AI score with rating +
    comment; overrides captured as labeled calibration data
  Scoring scale: 1-5 per competency (Section 9.2); raw scores NEVER shown
    to candidate, recruiter/panel only
  Basic report (M9-F01/F02): executive summary + Final Verdict per Section
    9.5 verdict bands (Strong Hire/Hire/Consider/Borderline/Reject)

Exit criteria: full submit -> score -> roll-up -> basic verdict pipeline
  runs end to end within report turnaround target (<5 min, Section 3).
Context7: use for LLM structured JSON scoring output.
PDCA: present plan before touching any file.
'@
    }

    # -- Phase 2 . Behavioral Intelligence & Integrity --------------------------
    "behavior-inference" = @{
        model = $SONNET
        task  = "TASK-002"
        label = "Phase 2 . Behavior Inference Engine (M7)"
        prompt = @'
Stack: FastAPI, PostgreSQL, LLM API
Task file: tasks/TASK-002-phase2-integrity.md
Module scope: agents/behavior_analysis ONLY.

Objective: Behavior Inference per PRD M7 (F01-F05).
  DISC Style Inference (M7-F01): from language patterns, decision framing,
    response structure across the FULL answer set -- NEVER from a direct
    "which of these describes you" question
  Big Five Inference (M7-F02): Openness, Conscientiousness, Extraversion,
    Agreeableness, Neuroticism/Emotional Stability from conversational evidence
  Leadership/Decision/Communication/Work Style (M7-F03): patterns across
    MULTIPLE answers, not any single question
  Stress Handling & EQ (M7-F04): use Stress-category questions + response
    degradation/recovery signal; EQ from Conflict Resolution/Teamwork answers
  Team Compatibility Signal (M7-F05): optional cross-reference against an
    org-level configured working style -- a discussion prompt for the
    recruiter, NEVER an automated pass/fail

Persist to behavior_profiles (disc_style jsonb, big_five jsonb,
  leadership_style, decision_style, communication_style, work_style,
  stress_signal, eq_signal, team_compatibility_signal).

IMPORTANT (Section 15): no facial recognition, no emotion-as-hiring-criterion,
  nothing tied to a protected characteristic -- exclude explicitly from prompts.

Exit criteria: behavior_profile generated for every completed session, 100%
  coverage without any self-report question in the set.
Context7: use for LLM structured JSON output.
PDCA: present plan before touching any file.
'@
    }

    "fraud-integrity" = @{
        model = $SONNET
        task  = "TASK-002"
        label = "Phase 2 . Fraud & Integrity Detection (M8)"
        prompt = @'
Stack: FastAPI, PostgreSQL + pgvector, embeddings, deterministic heuristics
Task file: tasks/TASK-002-phase2-integrity.md
Module scope: services/orchestrator-api/src/modules/integrity ONLY.
  (Deterministic + embedding-similarity checks alongside Evaluation Agent --
  NOT a separate conversational agent, per PRD Section 7.)

Objective: Fraud & Integrity Detection per PRD M8 (F01-F05).
  AI-Generated/Scripted Detection (M8-F01): statistical signatures -- uniform
    structure across answers, latency inconsistent with live thinking,
    phrasing divergent from the candidate's own earlier casual answers
  Duplicate/Near-Duplicate Detection (M8-F02): embedding similarity vs. the
    org's historical answer corpus (org-scoped, pgvector)
  Resume-Answer Consistency (M8-F03): cross-check interview claims against
    parsed resume (M2) -- flag claimed tech/projects absent from resume/
    portfolio evidence, or timeline conflicts
  Behavioral Signal Anomalies (M8-F04): for voice/video sessions only (future
    scope) -- long pauses, confidence mismatch, multi-speaker audio -- flags
    for human review only, NEVER automatic reject
  Integrity Summary (M8-F05): compile all flags into a report section with
    severity (Low/Medium/High) + specific evidence -- human makes the call

Persist to integrity_flags (flag_type enum, severity enum, evidence, nullable
  session_question_id).

Exit criteria: recall >85%, false-positive <10% on a labeled validation set
  (Section 3 goal -- flag as an open item if the labeled set doesn't exist yet,
  per Section 18 Open Question #4).
Context7: use for pgvector similarity queries, embedding APIs.
PDCA: present plan before touching any file.
'@
    }

    "hiring-report" = @{
        model = $SONNET
        task  = "TASK-002"
        label = "Phase 2 . Hiring Report Generator (M9, full) + Recommendation Agent"
        prompt = @'
Stack: FastAPI, PostgreSQL, LLM API, PDF export
Task file: tasks/TASK-002-phase2-integrity.md
Module scope: agents/recommendation + agents/report_generator +
  services/orchestrator-api/src/modules/reports (full) ONLY.

Objective: Full Hiring Report per PRD M9 (F01-F05), extending the Phase 1
  basic report with behavior + integrity enrichment.
  Executive Summary & Verdict (M9-F01): verdict always backed by reasoning,
    never a bare label -- bands per Section 9.5
  Full Report Sections (M9-F02): Candidate Overview, Resume Summary,
    Interview Summary, Technical/Leadership/Communication/Behavior scores,
    Culture Fit, Domain Knowledge, Skill Gap Analysis, Strengths, Weaknesses,
    Potential Risks, Learning Curve Estimate, Management Readiness, Promotion
    Potential, Salary Recommendation (BAND not a figure -- Section 18 Open
    Question #1, assume org-provided comp bands at MVP), Overall Rating,
    AI Confidence Score (Section 9.4 formula), Recommended Next Round,
    Training Needs, Suggested HR-Round Questions, Suggested CEO-Round
    Questions, Integrity Summary (M8), Final Verdict
  Benchmarking (M9-F03): every score relative to job's required bar AND
    (where available) org's historical hiring bar for the role family
  Export & Sharing (M9-F04): PDF export; scoped expiring share link to
    Client role, raw transcript hidden unless explicitly enabled
  Reviewer Feedback Loop (M9-F05): recruiter attaches final human decision +
    comment; discrepancies feed M6-F04 calibration dataset

Recommendation Agent synthesizes Scoring Agent + Behavior Analysis + Fraud
  outputs into salary band/verdict/training needs BEFORE Report Generator
  Agent composes the final document (pipeline order per Section 11.3).

Low AI Confidence Score routes to mandatory human review (Section 9.4, 15).

Exit criteria: full report generates within 5 min of submission; every score
  traceable to a quoted answer excerpt (Section 3 explainability goal).
Context7: use for LLM structured output, PDF generation library.
PDCA: present plan before touching any file.
'@
    }

    # -- Phase 5 (per PRD Section 16) . Dashboards / Analytics / Admin ---------
    dashboards = @{
        model = $HAIKU
        task  = "TASK-005"
        label = "Phase 5 . Dashboards (M10)"
        prompt = @'
Stack: Next.js (console-web + candidate-web), FastAPI, Recharts
Task file: tasks/TASK-005-phase5-dashboards-analytics.md
Module scope: apps/console-web/src/pages/dashboard +
  apps/candidate-web/src/pages/status ONLY.

Objective: Dashboards per PRD M10 (F01-F04).
  HR Dashboard (M10-F01): active assessments, candidates in progress,
    completed interviews awaiting review, pending final decisions, quick
    links into each report
  Candidate Dashboard (M10-F02): invitation status, interview instructions/
    modality, time remaining, post-completion status -- NEVER internal scores
  Admin Dashboard (M10-F03): org users/roles, competency library mgmt,
    department/role templates, billing/plan status
  Reports Dashboard (M10-F04): searchable/filterable archive of completed
    hiring reports, verdict + score-band filters

Reuse a shared SummaryCard/FilterBar/ChartCard pattern across all four --
  single source of truth, do not fork per dashboard.

Exit criteria: all four dashboards render from live API data; candidate view
  never exposes a raw score field.
Context7: use for Recharts, Next.js data fetching.
PDCA: present plan before touching any file.
'@
    }

    analytics = @{
        model = $SONNET
        task  = "TASK-005"
        label = "Phase 5 . Analytics (M11)"
        prompt = @'
Stack: FastAPI, PostgreSQL, Recharts, Redis (cached aggregates)
Task file: tasks/TASK-005-phase5-dashboards-analytics.md
Module scope: services/orchestrator-api/src/modules/analytics +
  apps/console-web/src/pages/analytics ONLY.

Objective: Analytics per PRD M11 (F01-F05).
  Score Trends (M11-F01): average scores over time, by department/skill/role
  Hiring Funnel (M11-F02): invited -> completed -> hired conversion, by
    department and role
  Question & Difficulty Analytics (M11-F03): category distribution, average
    difficulty mix, correlation between category coverage and eventual
    verdict -- feeds back into M4 category weighting tuning
  Candidate Benchmarking (M11-F04): percentile ranking vs. all other
    candidates assessed for the same role/level within the org
  Skill Trend & Hiring Prediction (M11-F05): top/weakest skill trends;
    predictive on-the-job-success signal is v2+ (Section 17) -- stub the
    data model, do not build the predictive model itself yet

Cache expensive aggregates in Redis; org-scoped everywhere except cross-org
  Admin analytics views.

Exit criteria: all four funnel/trend views load from real session data with
  correct org scoping.
Context7: use for Postgres aggregation, Recharts.
PDCA: present plan before touching any file.
'@
    }

    admin = @{
        model = $SONNET
        task  = "TASK-005"
        label = "Phase 5 . Platform Administration (M12)"
        prompt = @'
Stack: FastAPI, PostgreSQL, Next.js (console-web)
Task file: tasks/TASK-005-phase5-dashboards-analytics.md
Module scope: services/orchestrator-api/src/modules/admin +
  packages/prompt-library ONLY. Admin-only routes, cross-tenant.

Objective: Platform Administration per PRD M12 (F01-F04).
  Tenant & Workspace Management (M12-F01): Super Admin provisions org
    workspaces, manages plan tiers, monitors per-tenant usage
  Prompt Library Management (M12-F02): central versioned repository of every
    agent's prompt templates, with rollout/rollback controls per tenant or
    globally -- every generated question/score must be traceable to the exact
    prompt version that produced it (Section 10 Observability requirement)
  Model Routing Configuration (M12-F03): which LLM/model powers each agent
    (question generation vs. report writing vs. deterministic scoring may
    reasonably differ), with fallback routing on provider outage
  System Health & Incident Monitoring (M12-F04): queue depth, generation
    latency p50/p95/p99, agent error rates, fraud-flag false-positive tracking

Exit criteria: prompt version rollback works without downtime; model routing
  change takes effect on next agent invocation without a redeploy.
Context7: use for FastAPI admin routing patterns.
PDCA: present plan before touching any file.
'@
    }

    # -- Frontend Shells ---------------------------------------------------------
    "frontend-candidate" = @{
        model = $SONNET
        task  = "TASK-001"
        label = "Web . Candidate Interview Runtime Shell"
        prompt = @'
Stack: Next.js, TypeScript, Tailwind CSS
Task file: tasks/TASK-001-phase1-question-test.md
Module scope: apps/candidate-web/ ONLY.

Objective: Candidate-facing shell per PRD Section 11.1 + Section 10 (Usability
  / Accessibility).
  Minimal, low-distraction UI -- login (passwordless) -> consent capture
  (Section 15, AFTER login, BEFORE interview starts) -> test runtime
  (M5-F02) -> submitted/status screen (M10-F02, no scores exposed)
  Degrades gracefully to text-only if voice/video fails mid-session, without
  losing scoring continuity (future-proofing for Section 17 voice/video --
  do not build voice/video now, just don't block it structurally)
  WCAG 2.1 AA compliance
  Typed API client; candidate JWT scoped to a single assessment_session

Exit criteria: full login -> consent -> test -> submit -> status flow works
  on standard broadband; accessibility audit passes AA.
Context7: use for Next.js App Router, accessible form patterns.
PDCA: present plan before touching any file.
'@
    }

    "frontend-console" = @{
        model = $SONNET
        task  = "TASK-000"
        label = "Web . HR/Admin/Analytics Console Shell"
        prompt = @'
Stack: Next.js, TypeScript, Tailwind CSS, Recharts
Task file: tasks/TASK-000-phase0-foundation.md
Module scope: apps/console-web/ ONLY.

Objective: Console shell per PRD Section 11.1 (dense, data-rich UI for
  HR/Admin/Analytics).
  Main nav covering the modules: Job Assessments (M1), Candidates/Sessions,
    Reports (M10-F04), Analytics (M11), Admin (M10-F03/M12)
  SHARED components reused across every list screen (single source of
    truth): SummaryCard, FilterBar, ChartCard, ReportCard
  Typed API client + JWT auth/refresh handling; route guards mirror server
    RBAC (Section 4.2) -- User vs. Admin route visibility
  Responsive: desktop-first, tablet functional

Exit criteria: shell navigable across all module stubs; RBAC-gated routes
  correctly hide Admin-only sections from User role.
Context7: use for Next.js App Router, Recharts, RBAC route-guard patterns.
PDCA: present plan before touching any file.
'@
    }

    # -- Debug -----------------------------------------------------------------
    debug = @{
        model = $SONNET
        task  = "TASK-???"
        label = "Debug Session"
        prompt = @'
Stack: FastAPI (Python), PostgreSQL + pgvector, Redis, Next.js/TypeScript, JWT
Task: one error, one file, one session.

Paste in order:
  1. Full stack trace / error message
  2. Only the function or endpoint that threw it
  3. Relevant table schema / Pydantic model if DB-related

Known project gotchas:
  - Every query MUST be scoped to org_id except explicit Admin cross-tenant routes
  - Candidate JWT scoped to ONE assessment_session; Client JWT scoped to ONE
    report_share -- never treat either as a general-purpose account session
  - role/scope claims come from JWT payload -- never from request body
  - Question generation is UPFRONT + BATCH only -- no live/turn-by-turn AI
    interaction during the test (Section 8); don't reintroduce that pattern
  - M4-F05 no-repeat check is ORG-SCOPED pgvector similarity, not global
  - Raw competency scores (1-5) are NEVER shown to candidates
  - Every score must stay traceable to a prompt_templates version + a quoted
    answer excerpt (Section 10 Observability / Section 15 Explainability)
  - No biometric/emotion-based signals anywhere in agent prompts (Section 15)

PDCA: diagnose first, present fix plan, wait for approval before editing.
'@
    }
}

# -- LIST MODE -----------------------------------------------------------------
if ($Session -eq "list") {
    Write-Host ""
    Write-Host "  ARAP -- Available Sessions" -ForegroundColor Cyan
    Write-Host ""
    Write-Host ("  {0,-22} {1,-46} {2}" -f "SESSION", "LABEL", "MODEL") -ForegroundColor DarkGray
    Write-Host ("  {0,-22} {1,-46} {2}" -f "----------------------", "----------------------------------------------", "----------") -ForegroundColor DarkGray
    foreach ($key in $sessions.Keys | Sort-Object) {
        $s = $sessions[$key]
        $tag = if ($s.model -like "*haiku*") { "Haiku  [G]" } else { "Sonnet [B]" }
        Write-Host ("  {0,-22} {1,-46} [{2}]" -f $key, $s.label, $tag)
    }
    Write-Host ""
    exit 0
}

# -- LAUNCH SESSION ------------------------------------------------------------
$s = $sessions[$Session]

Write-Host ""
Write-Host "  +------------------------------------------------------+" -ForegroundColor Cyan
Write-Host ("  |  {0,-52}|" -f $s.label) -ForegroundColor Cyan
Write-Host ("  |  Task:  {0,-48}|" -f $s.task) -ForegroundColor Cyan
Write-Host ("  |  Model: {0,-48}|" -f $s.model) -ForegroundColor Cyan
Write-Host "  +------------------------------------------------------+" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Context:" -ForegroundColor DarkGray
Write-Host $s.prompt -ForegroundColor White
Write-Host ""

$s.prompt | Set-Clipboard
Write-Host "  v Context copied to clipboard." -ForegroundColor Green
Write-Host "  -> Paste into Claude Code, then type: superpowers brainstorm" -ForegroundColor Cyan
Write-Host ""

Set-Location $PROJECT_ROOT
$env:ANTHROPIC_MODEL = $s.model
claude --model $s.model

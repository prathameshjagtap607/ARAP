# M5 — Test Delivery Design Spec
**Date:** 2026-07-24  
**Task:** TASK-001 Phase 1 — M5  
**PRD ref:** Section 16, Phase 1; PRD §10 (WCAG), §17 (deferred formats)  
**Status:** Approved  
**Scope:** `apps/candidate-web/src` + `services/orchestrator-api/src/modules/sessions`

---

## 1. Objective

Ship the candidate-facing test delivery layer end-to-end:

- Recruiter triggers an emailed magic link once the question set is locked (M5-F01)
- Candidate logs in passwordlessly, takes the test one question at a time with free navigation (M5-F02)
- Supports `multiple_choice`, `short_text`, `long_text` answer formats (M5-F03)
- Session is bounded by `time_budget_seconds`; server auto-submits on expiry (M5-F04)
- Every answered question is persisted to DB immediately; reconnect rehydrates full state (M5-F05)

Out of scope: voice, video, coding-sandbox formats (PRD §17); adaptive branching; live AI interaction.

---

## 2. Architecture

```
candidate-web (Next.js App Router)     orchestrator-api (FastAPI)
──────────────────────────────────     ──────────────────────────
/assessment/[sessionId]/               POST /auth/candidate/verify-token  (existing)
  LoginPage                            GET  /sessions/{id}                 (new)
  ConsentPage                          POST /sessions/{id}/start           (new)
  QuestionPage                         PATCH /sessions/{id}/questions/{qid}/answer  (new)
  SubmittedPage                        POST /sessions/{id}/submit          (new)
                                       POST /sessions/{session_id}/invite  (new)
```

All candidate-web pages are client components. No SSR data fetching — state is React + REST. JWT stored in React memory (never localStorage).

---

## 3. Backend — `sessions` Module

### 3.1 File layout

```
services/orchestrator-api/src/modules/sessions/
  __init__.py
  router.py     FastAPI routes + auth dependency
  service.py    Business logic
  schemas.py    Pydantic request/response models
  email.py      send_invite_email() util
```

### 3.2 Config additions (`src/config.py`)

```python
CANDIDATE_PORTAL_URL: str = "http://localhost:3001"
SMTP_HOST: str = ""
SMTP_PORT: int = 587
SMTP_USER: str = ""
SMTP_PASSWORD: str = ""
SMTP_FROM: str = "noreply@arap.dev"
SENDGRID_API_KEY: str = ""   # takes precedence over SMTP when set
```

If neither SMTP nor SendGrid is configured, `send_invite_email` logs a warning and prints the link to stdout (dev mode). The invite endpoint always returns the link in its response body.

### 3.3 Endpoints

#### `POST /sessions/{session_id}/invite`
- Auth: recruiter JWT (`role in ["user","admin"]`)
- Calls existing `auth.service.request_candidate_token()` to generate raw token
- Composes `{CANDIDATE_PORTAL_URL}/assessment/{session_id}?token={raw}`
- Calls `send_invite_email(to, link, job_title, duration_minutes)`
- Returns `{ "link": "...", "email_sent": bool }`
- Constraint: question set must be locked (`locked_at IS NOT NULL`); raises 409 otherwise

#### `GET /sessions/{id}`
- Auth: candidate JWT with matching `assessment_session_id` claim
- Returns: `status`, `seconds_remaining` (computed: `time_budget_seconds - seconds_since_started_at`; null if not started), `questions[]` with saved `answer_text` and `answered_at`
- Questions ordered by `sequence_no`

#### `POST /sessions/{id}/start`
- Auth: candidate JWT
- Sets `started_at = now()`, transitions `invited → in_progress`
- Idempotent: if already `in_progress`, returns current state unchanged
- Rejects if `completed` or `expired`

#### `PATCH /sessions/{id}/questions/{qid}/answer`
- Auth: candidate JWT
- Validates `answer_format` matches submitted payload shape:
  - `multiple_choice`: `selected_option` (str, must be in `options` keys)
  - `short_text` / `long_text`: `answer_text` (str, non-empty)
- Writes `answer_text` + `answered_at = now()` to `session_questions` row
- Rejects with 409 if session is `completed` or `expired`
- Returns saved question row

#### `POST /sessions/{id}/submit`
- Auth: candidate JWT
- Timer check: if `now() > started_at + time_budget_seconds` → status becomes `expired` only if zero answers exist, else `completed`
- Sets `completed_at = now()`, `status = completed` (or `expired`)
- Accepts partial answers (auto-submit path from timer expiry)
- Stubs evaluation enqueue (logs session_id; M6 will hook here)
- Idempotent: if already `completed`/`expired`, returns current state

### 3.4 Timer enforcement rule

Server computes expiry at two points:
1. `GET /sessions/{id}` — returns `seconds_remaining` for client countdown seed
2. `POST /sessions/{id}/submit` — enforces deadline; a client submitting seconds late still completes

Client submitting after expiry: accepted, transitions to `completed` if any answers exist. This matches PRD "auto-submit whatever is answered."

---

## 4. Frontend — `candidate-web` Routes

### 4.1 Route structure

```
apps/candidate-web/src/app/assessment/[sessionId]/
  page.tsx            LoginPage
  consent/page.tsx    ConsentPage
  test/page.tsx       QuestionPage
  done/page.tsx       SubmittedPage
```

### 4.2 State (`useSessionStore` — `useReducer` + Context)

```ts
interface SessionState {
  jwt: string | null
  session: {
    id: string
    status: string
    secondsRemaining: number
    totalSeconds: number
    jobTitle: string
  } | null
  questions: Question[]
  answers: Record<string, string>   // questionId → answer_text
  currentIndex: number
  submitting: boolean
}
```

### 4.3 Page behaviours

**LoginPage** (`page.tsx`)
- Pre-fills `sessionId` from URL path; reads `token` from query param
- Email input → `POST /auth/candidate/verify-token` → stores JWT in context
- On success → redirects to `/consent`

**ConsentPage** (`consent/page.tsx`)
- Calls `GET /sessions/{id}` to show job title and duration
- Displays T&C checkbox (required)
- "Start Assessment" → `POST /sessions/{id}/start` → redirects to `/test`

**QuestionPage** (`test/page.tsx`)
- On mount: `GET /sessions/{id}` → rehydrates `answers` from server, seeds timer from `seconds_remaining`
- Reconnect: `window.addEventListener('online', refetch)` triggers same GET
- Renders one question at a time (current index)
- Navigation: Prev / Next buttons + numbered pill nav (all questions accessible)
- Answer formats:
  - `multiple_choice` → `<fieldset>` + radio group from `options` JSONB
  - `short_text` → `<input type="text">`
  - `long_text` → `<textarea>`
- Save trigger: radio `onChange` (MCQ); text `onBlur` (short/long) → `PATCH …/answer` → update local `answers` on 200
- Timer: `useEffect` countdown; `aria-live="polite"` region announces every 60s and final 60s countdown
- At t=0: calls `POST /sessions/{id}/submit` → redirects to `/done`
- Manual submit button: visible only when all questions have an answer in local state

**SubmittedPage** (`done/page.tsx`)
- Static thank-you message, no score shown (PRD: candidate dashboard never exposes raw score)

### 4.4 WCAG 2.1 AA compliance

- All inputs have `<label htmlFor>`
- Focus ring never suppressed (`outline: revert` in globals)
- Color contrast ≥ 4.5:1 (slate palette)
- Timer announced via `aria-live="polite"`
- No motion without `prefers-reduced-motion` check on any animated elements

---

## 5. Email Link & Token Flow

```
1. Question set locked (M4)
2. Recruiter: POST /sessions/{session_id}/invite
3. Server: request_candidate_token() → raw token
4. Link: {CANDIDATE_PORTAL_URL}/assessment/{session_id}?token={raw}
5. send_invite_email(to=candidate.email, link, job_title, duration_minutes)
6. Candidate clicks → LoginPage pre-fills session_id, token
7. Candidate enters email → POST /auth/candidate/verify-token → JWT
8. JWT in React context (memory only)
9. All API calls: Authorization: Bearer {jwt}
```

---

## 6. Save & Resume (M5-F05)

- `PATCH …/answer` is synchronous DB write; frontend advances state only on 200
- Network drop: local answer state preserved in React; on reconnect GET rehydrates from DB
- Already-saved answers are never overwritten by reconnect rehydration (server values win only for answers not yet saved locally)
- `secondsRemaining` reseeded from server on reconnect (prevents client clock drift)

---

## 7. Exit Criteria Coverage

| Criterion | Mechanism |
|---|---|
| Login via emailed link | `/invite` → token in URL → verify-token → JWT |
| DISC-style Q&A | One question at a time, prev/next navigation, no adaptive branching |
| Answer formats | MCQ radio, short text input, long text textarea |
| Time-bound window | Server enforces at start+submit; client countdown seeded from server |
| Auto-submit at expiry | `useEffect` at t=0 → POST /submit; server enforces deadline independently |
| Disconnect safe | `online` event → GET /sessions rehydrates full answer state from DB |
| No score shown to candidate | SubmittedPage is static thank-you only |

---

## 8. Out of Scope

- Voice, video, coding-sandbox answer formats (PRD §17)
- Adaptive branching or live AI during test
- Candidate dashboard score display (M10)
- Evaluation scoring (M6 — stub only in submit endpoint)

# Candidate Web Shell — Design Spec

**Date:** 2026-07-24
**Task:** TASK-001 — candidate-facing shell (M10-F02 + WCAG + §15 consent)
**PRD refs:** §10 (WCAG 2.1 AA), §11.1 (candidate UI shell), §15 (consent), §17 (deferred voice/video)
**Status:** Approved
**Scope:** `apps/candidate-web/src/` ONLY — no API changes, no new routes

---

## 1. Objective

Close the gap between the functional M5 shell (built in the test-delivery session) and the stated exit criteria:

- WCAG 2.1 AA accessibility audit passes
- PRD §15 data-processing consent captured before test starts
- M10-F02 candidate status screen shows "Under Review" with context after submission
- `AnswerFormat` type is structurally extensible for PRD §17 voice/video/code without blocking current functionality

The full flow already works end-to-end. This session fixes correctness, accessibility, and polish — no new backend endpoints.

---

## 2. Gaps Being Closed

| Gap | Root cause | Fix |
|-----|-----------|-----|
| `text-slate-500` (#64748b) fails AA contrast (3.95:1) | M5 used slate-500 for secondary text; M5 spec said "≥ 4.5:1" | Replace with `text-slate-600` (#475569, 5.74:1) on all content text |
| Timer `aria-live` fires every second | M5 spec said "every 60s + final 60s countdown"; not implemented | Rate-limit live region updates to every 60s and at ≤60s mark |
| No skip-to-content link | Never added | Add to root layout; add `id="main-content"` to each `<main>` |
| No per-route `<title>` update | Client components can't use metadata export | Add `useEffect` title update in each page |
| No `prefers-reduced-motion` guard | M5 spec mentioned it; nothing in CSS | Single CSS rule in globals.css |
| Consent: missing data-processing disclosure | M5 only added T&C checkbox | Add second required checkbox per PRD §15 |
| `done/page.tsx` is boilerplate | M10-F02 not yet implemented | Rich static status screen with job title + "Under Review" |
| `AnswerFormat` has no future variants | PRD §17 deferred; type never extended | Add `video | voice | code` variants + text fallback in renderer |

---

## 3. File Changes

### 3.1 `src/app/globals.css`

Add after the existing focus-visible rules:

```css
@media (prefers-reduced-motion: reduce) {
  *, ::before, ::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }
}
```

### 3.2 `src/app/layout.tsx`

Add a skip link as the first child of `<body>`:

```tsx
<a
  href="#main-content"
  className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4
             focus:z-50 focus:rounded focus:bg-white focus:px-4 focus:py-2
             focus:text-slate-900 focus:shadow-lg focus:outline focus:outline-2
             focus:outline-slate-900"
>
  Skip to main content
</a>
```

### 3.3 `src/lib/types.ts`

Extend `AnswerFormat`:

```ts
export type AnswerFormat =
  | "multiple_choice"
  | "short_text"
  | "long_text"
  | "video"   // PRD §17 — deferred
  | "voice"   // PRD §17 — deferred
  | "code";   // PRD §17 — deferred
```

No other type changes needed.

### 3.4 `src/app/assessment/[sessionId]/page.tsx` (LoginPage)

- Add `id="main-content"` to `<main>`
- Replace `text-slate-500` with `text-slate-600`
- Add `useEffect(() => { document.title = 'Access Your Assessment | ARAP' }, [])`

### 3.5 `src/app/assessment/[sessionId]/consent/page.tsx` (ConsentPage)

- Add `id="main-content"` to `<main>`
- Replace `text-slate-500` with `text-slate-600`
- Add `useEffect(() => { document.title = 'Assessment Terms | ARAP' }, [])`
- Add second required checkbox (PRD §15):

```tsx
const [agreedData, setAgreedData] = useState(false);
// ...
<div className="flex items-start gap-3">
  <input
    id="consent-data"
    type="checkbox"
    checked={agreedData}
    onChange={(e) => setAgreedData(e.target.checked)}
    className="mt-1"
  />
  <label htmlFor="consent-data" className="text-sm text-slate-700">
    I understand my responses will be evaluated using AI analysis and processed
    in accordance with the applicable privacy policy.
  </label>
</div>
// Start button disabled until both agreed && agreedData
```

### 3.6 `src/app/assessment/[sessionId]/test/page.tsx` (QuestionPage)

- Add `id="main-content"` to `<main>`
- Replace `text-slate-500` with `text-slate-600`
- Add `useEffect(() => { document.title = 'Assessment In Progress | ARAP' }, [])`
- Replace `text-slate-500` on saving/error hints
- Fix timer `aria-live` — rate-limit announcements:

```tsx
// separate state for announced value (drives the live region text)
const [announcedTime, setAnnouncedTime] = useState<string | null>(null);

// in the countdown useEffect, after decrement:
// announce at every 60s boundary AND when ≤ 60s remaining
const shouldAnnounce = next % 60 === 0 || next <= 60;
if (shouldAnnounce) setAnnouncedTime(formatTime(next));
```

The visible timer still updates every second. Only `announcedTime` (in the `aria-live` region) is rate-limited.

- Add text-only fallback in question renderer for deferred formats:

```tsx
{/* fallback for PRD §17 deferred formats (video/voice/code) */}
{!["multiple_choice","short_text","long_text"].includes(current.answer_format) && (
  <div key={current.id}>
    <p className="text-sm text-slate-600 mb-2">
      Please provide your response in text form below.
    </p>
    <label htmlFor={`fallback-${current.id}`} className="sr-only">Your answer</label>
    <textarea
      id={`fallback-${current.id}`}
      rows={6}
      defaultValue={state.answers[current.id] ?? ""}
      onBlur={(e) => saveAnswer(current.id, e.target.value)}
      className="w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900
                 focus:outline focus:outline-2 focus:outline-slate-900 resize-y"
    />
  </div>
)}
```

### 3.7 `src/app/assessment/[sessionId]/done/page.tsx` (SubmittedPage — M10-F02)

Replace the static boilerplate with a proper status screen. The page reads from `SessionContext` for the job title (available if the candidate hasn't refreshed; graceful fallback if lost). No polling — `completed` is a terminal state; hiring decision is communicated out-of-band.

```tsx
"use client";
import { useEffect } from "react";
import { useSession } from "@/context/SessionContext";

export default function SubmittedPage() {
  const { state } = useSession();
  const jobTitle = state.session?.job_title ?? "Your Assessment";

  useEffect(() => {
    document.title = "Submitted | ARAP";
  }, []);

  return (
    <main id="main-content" className="flex min-h-screen flex-col items-center justify-center px-6">
      <div className="max-w-md w-full space-y-6">
        <div className="flex items-center gap-3">
          <span
            className="inline-flex items-center rounded-full bg-amber-100 px-3 py-1
                       text-sm font-medium text-amber-800"
            aria-label="Status: Under Review"
          >
            Under Review
          </span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          {jobTitle} — Submitted
        </h1>
        <p className="text-slate-600">
          Thank you for completing your assessment. Your responses are being reviewed
          by the hiring team.
        </p>
        <p className="text-sm text-slate-600">
          You will be contacted with next steps. Results are typically reviewed
          within 2–3 business days.
        </p>
      </div>
    </main>
  );
}
```

---

## 4. WCAG 2.1 AA Coverage

| Criterion | Mechanism |
|-----------|-----------|
| 1.4.3 Contrast (minimum) | `text-slate-600` (#475569) on white = 5.74:1 ≥ 4.5:1 |
| 1.3.1 Info and relationships | `<fieldset>`/`<legend>` for MCQ; `<label htmlFor>` on all inputs |
| 2.4.1 Bypass blocks | Skip-to-content link in root layout |
| 2.4.2 Page titled | `document.title` updated on each route |
| 2.4.3 Focus order | Logical DOM order; no `tabindex` manipulation |
| 2.4.7 Focus visible | `outline: revert` + `focus-visible` rules in globals.css |
| 4.1.3 Status messages | `role="alert"` on error paragraphs; `aria-live="polite"` on timer |
| 1.4.12 Text spacing | Tailwind default spacing; no fixed-height clipping |
| 2.3.3 Animation from interactions | `prefers-reduced-motion` rule in globals.css |

---

## 5. PRD §17 Voice/Video Structural Readiness

- `AnswerFormat` union includes `video | voice | code` as typed but unrendered variants
- `QuestionPage` has an explicit text-fallback branch for any format not in the current render set
- The fallback captures a text answer and passes it through the existing `saveAnswer` path — scoring continuity is preserved
- No other structural changes needed; adding a new answer format renderer is a self-contained addition to the switch block

---

## 6. Exit Criteria Coverage

| Criterion | Mechanism |
|-----------|-----------|
| Full login → consent → test → submit → status flow works | Existing M5 flow unchanged; status screen upgraded |
| Accessibility audit passes AA | All WCAG gaps listed in §2 closed by changes in §3 |
| Consent captured per §15 | Two-checkbox gate: T&C + data-processing |
| M10-F02: no raw scores exposed | Done page shows status badge + message only |
| Voice/video not blocked structurally | AnswerFormat extended; text fallback in renderer |

---

## 7. Out of Scope

- Any backend API changes
- New routes or pages
- Polling for report status (hiring decision is out-of-band; `GET /reports/{session_id}` is `require_user` only)
- Voice, video, coding-sandbox rendering (PRD §17 — future session)
- Analytics or admin screens

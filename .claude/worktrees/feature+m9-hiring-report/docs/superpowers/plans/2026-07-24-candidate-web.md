# Candidate Web Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close WCAG 2.1 AA gaps, add PRD §15 data-processing consent, implement M10-F02 status screen, and extend AnswerFormat for future voice/video — all within `apps/candidate-web/src/`.

**Architecture:** Seven files modified in-place; no new files, no new routes, no API changes. The M5 flow (login → consent → test → done) is fully functional — this plan fixes correctness, accessibility, and the M10-F02 done screen. Tasks are ordered foundation-first so each builds cleanly on the last.

**Tech Stack:** Next.js 14.2.5 (App Router), React 18, TypeScript 5, Tailwind CSS 3. No test framework — verification uses `tsc --noEmit`, `next lint`, and `next build`.

## Global Constraints

- Scope: `apps/candidate-web/src/` ONLY — no files outside this directory
- No new npm packages
- No API changes
- All `<main>` elements must have `id="main-content"` (skip-link target)
- Secondary text uses `text-slate-600` (#475569, 5.74:1 on white) — never `text-slate-500`
- `document.title` set via `useEffect` in every page (client components cannot export `metadata`)
- Run all verification commands from `apps/candidate-web/` directory

---

## File Map

| File | Change type | What changes |
|------|-------------|--------------|
| `src/app/globals.css` | Modify | Add `prefers-reduced-motion` rule |
| `src/app/layout.tsx` | Modify | Add skip-to-content link |
| `src/lib/types.ts` | Modify | Extend `AnswerFormat` with future variants |
| `src/app/assessment/[sessionId]/page.tsx` | Modify | WCAG: title, contrast, `id="main-content"` |
| `src/app/assessment/[sessionId]/consent/page.tsx` | Modify | WCAG fixes + PRD §15 second checkbox |
| `src/app/assessment/[sessionId]/test/page.tsx` | Modify | WCAG fixes + timer aria-live rate-limit + §17 fallback |
| `src/app/assessment/[sessionId]/done/page.tsx` | Rewrite | M10-F02 status screen |

---

### Task 1: Foundation — globals.css + layout.tsx + types.ts

**Files:**
- Modify: `apps/candidate-web/src/app/globals.css`
- Modify: `apps/candidate-web/src/app/layout.tsx`
- Modify: `apps/candidate-web/src/lib/types.ts`

**Interfaces:**
- Produces: `AnswerFormat` union with `video | voice | code` variants (consumed by Task 4)
- Produces: skip link in root layout (all pages inherit it)

- [ ] **Step 1: Add prefers-reduced-motion rule to globals.css**

Open `src/app/globals.css`. Append after the existing `*:focus-visible` block:

```css
@media (prefers-reduced-motion: reduce) {
  *, ::before, ::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }
}
```

Full file after edit:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --background: #ffffff;
  --foreground: #0f172a;
}

body {
  background: var(--background);
  color: var(--foreground);
  font-family: Inter, ui-sans-serif, system-ui, sans-serif;
}

/* WCAG 2.1 AA — never suppress focus rings */
*:focus {
  outline: revert;
}
*:focus:not(:focus-visible) {
  outline: none;
}
*:focus-visible {
  outline: 2px solid #0f172a;
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  *, ::before, ::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 2: Add skip link to layout.tsx**

Replace `src/app/layout.tsx` with:

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ARAP — Candidate Assessment",
  description: "AI Recruitment Assessment Platform — Candidate Portal",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-slate-900 antialiased">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4
                     focus:z-50 focus:rounded focus:bg-white focus:px-4 focus:py-2
                     focus:text-slate-900 focus:shadow-lg focus:outline focus:outline-2
                     focus:outline-slate-900"
        >
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 3: Extend AnswerFormat in types.ts**

Replace the `AnswerFormat` type in `src/lib/types.ts`:

```ts
export type AnswerFormat =
  | "multiple_choice"
  | "short_text"
  | "long_text"
  | "video"   // PRD §17 — deferred
  | "voice"   // PRD §17 — deferred
  | "code";   // PRD §17 — deferred
```

Full file after edit:

```ts
export type AnswerFormat =
  | "multiple_choice"
  | "short_text"
  | "long_text"
  | "video"   // PRD §17 — deferred
  | "voice"   // PRD §17 — deferred
  | "code";   // PRD §17 — deferred

export interface Question {
  id: string;
  sequence_no: number;
  question: { text: string; options?: Record<string, string> };
  category: string;
  target_competencies: string[];
  difficulty: string;
  answer_format: AnswerFormat;
  options: Record<string, string> | null;
  answer_text: string | null;
  answered_at: string | null;
}

export interface SessionData {
  id: string;
  status: "invited" | "in_progress" | "completed" | "expired";
  seconds_remaining: number | null;
  time_budget_seconds: number;
  job_title: string;
  duration_minutes: number;
  questions: Question[];
}

export interface SessionState {
  jwt: string | null;
  session: SessionData | null;
  answers: Record<string, string>;
  currentIndex: number;
  submitting: boolean;
}

export type SessionAction =
  | { type: "SET_JWT"; jwt: string }
  | { type: "SET_SESSION"; session: SessionData }
  | { type: "SET_ANSWER"; questionId: string; text: string }
  | { type: "SET_INDEX"; index: number }
  | { type: "SET_SUBMITTING"; value: boolean }
  | { type: "REHYDRATE"; session: SessionData };
```

- [ ] **Step 4: TypeScript check**

```bash
cd apps/candidate-web && npx tsc --noEmit
```

Expected: no errors. If you see "cannot find module" errors, run `pnpm install` from repo root first.

- [ ] **Step 5: Commit**

```bash
git add apps/candidate-web/src/app/globals.css \
        apps/candidate-web/src/app/layout.tsx \
        apps/candidate-web/src/lib/types.ts
git commit -m "[TASK-001] feat(candidate-web): WCAG foundation — skip link, reduced-motion, AnswerFormat extension"
```

---

### Task 2: LoginPage WCAG Fixes

**Files:**
- Modify: `apps/candidate-web/src/app/assessment/[sessionId]/page.tsx`

**Interfaces:**
- Consumes: nothing new — existing `apiFetch`, `useSession`, Next.js hooks
- Produces: login page with `id="main-content"`, correct contrast, page title

- [ ] **Step 1: Replace LoginPage**

Replace `src/app/assessment/[sessionId]/page.tsx` with:

```tsx
"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/context/SessionContext";

export default function LoginPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { dispatch } = useSession();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    document.title = "Access Your Assessment | ARAP";
  }, []);

  const token = searchParams.get("token") ?? "";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const data = await apiFetch<{ access_token: string }>(
        "/auth/candidate/verify-token",
        {
          method: "POST",
          body: JSON.stringify({ token, assessment_session_id: sessionId }),
        }
      );
      dispatch({ type: "SET_JWT", jwt: data.access_token });
      router.push(`/assessment/${sessionId}/consent`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main id="main-content" className="flex min-h-screen flex-col items-center justify-center px-6">
      <div className="max-w-md w-full space-y-6">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Access Your Assessment
        </h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <p className="text-sm text-slate-600">
            Click continue to access your assessment. Your identity is verified
            by the secure link in your invitation email.
          </p>
          {error && (
            <p role="alert" className="text-sm text-red-600">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-slate-900 px-6 py-3 text-white font-medium
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? "Verifying…" : "Continue"}
          </button>
        </form>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: TypeScript + lint check**

```bash
cd apps/candidate-web && npx tsc --noEmit && npm run lint
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add apps/candidate-web/src/app/assessment/[sessionId]/page.tsx
git commit -m "[TASK-001] fix(candidate-web): LoginPage — WCAG contrast, page title, main landmark"
```

---

### Task 3: ConsentPage WCAG + PRD §15

**Files:**
- Modify: `apps/candidate-web/src/app/assessment/[sessionId]/consent/page.tsx`

**Interfaces:**
- Consumes: `SessionData` (unchanged), `useSession`, `apiFetch`
- Produces: consent page with two required checkboxes (T&C + data-processing per §15), correct contrast, page title, `id="main-content"`

- [ ] **Step 1: Replace ConsentPage**

Replace `src/app/assessment/[sessionId]/consent/page.tsx` with:

```tsx
"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/context/SessionContext";
import type { SessionData } from "@/lib/types";

export default function ConsentPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const router = useRouter();
  const { state, dispatch } = useSession();
  const [agreed, setAgreed] = useState(false);
  const [agreedData, setAgreedData] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Assessment Terms | ARAP";
  }, []);

  useEffect(() => {
    if (!state.jwt) return;
    apiFetch<SessionData>(`/sessions/${sessionId}`, { jwt: state.jwt })
      .then((data) => dispatch({ type: "SET_SESSION", session: data }))
      .catch(() => {});
  }, [state.jwt, sessionId, dispatch]);

  async function handleStart() {
    if (!state.jwt) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<SessionData>(`/sessions/${sessionId}/start`, {
        method: "POST",
        jwt: state.jwt,
      });
      dispatch({ type: "SET_SESSION", session: data });
      router.push(`/assessment/${sessionId}/test`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start");
    } finally {
      setLoading(false);
    }
  }

  const session = state.session;

  return (
    <main id="main-content" className="flex min-h-screen flex-col items-center justify-center px-6">
      <div className="max-w-md w-full space-y-6">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          {session?.job_title ?? "Assessment"}
        </h1>
        <ul className="text-slate-600 space-y-1 text-sm list-disc list-inside">
          <li>Duration: {session?.duration_minutes ?? "—"} minutes</li>
          <li>Questions: {session?.questions.length ?? "—"}</li>
          <li>You may navigate between questions before submitting.</li>
          <li>Your progress is saved after each answer.</li>
        </ul>
        <div className="space-y-3">
          <div className="flex items-start gap-3">
            <input
              id="consent"
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              className="mt-1"
            />
            <label htmlFor="consent" className="text-sm text-slate-700">
              I confirm this is my own work and I agree to the assessment terms.
            </label>
          </div>
          <div className="flex items-start gap-3">
            <input
              id="consent-data"
              type="checkbox"
              checked={agreedData}
              onChange={(e) => setAgreedData(e.target.checked)}
              className="mt-1"
            />
            <label htmlFor="consent-data" className="text-sm text-slate-700">
              I understand my responses will be evaluated using AI analysis and
              processed in accordance with the applicable privacy policy.
            </label>
          </div>
        </div>
        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
        <button
          onClick={handleStart}
          disabled={!agreed || !agreedData || loading}
          className="w-full rounded-lg bg-slate-900 px-6 py-3 text-white font-medium
                     disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? "Starting…" : "Start Assessment"}
        </button>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: TypeScript + lint check**

```bash
cd apps/candidate-web && npx tsc --noEmit && npm run lint
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add apps/candidate-web/src/app/assessment/[sessionId]/consent/page.tsx
git commit -m "[TASK-001] feat(candidate-web): ConsentPage — PRD §15 data-processing checkbox, WCAG fixes"
```

---

### Task 4: QuestionPage — WCAG + Timer Fix + §17 Fallback

**Files:**
- Modify: `apps/candidate-web/src/app/assessment/[sessionId]/test/page.tsx`

**Interfaces:**
- Consumes: `AnswerFormat` (now includes future variants from Task 1), `Question`, `SessionData`, `useSession`, `apiFetch`
- Produces: question page with rate-limited `aria-live` timer, `id="main-content"`, correct contrast, page title, text fallback for unknown answer formats

**Key changes:**
- `announcedTime` state (separate from `secondsLeft`) drives the `aria-live` region
- A `useEffect` watching `secondsLeft` updates `announcedTime` only at `secondsLeft % 60 === 0` or `secondsLeft <= 60`
- Visible timer div gets `aria-hidden="true"` — screen readers use the sr-only live region instead
- Fallback render branch catches any `answer_format` that is not one of the three known values

- [ ] **Step 1: Replace QuestionPage**

Replace `src/app/assessment/[sessionId]/test/page.tsx` with:

```tsx
"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/context/SessionContext";
import type { Question, SessionData } from "@/lib/types";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60).toString().padStart(2, "0");
  const s = (seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

export default function QuestionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const router = useRouter();
  const { state, dispatch } = useSession();
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const [announcedTime, setAnnouncedTime] = useState<string | null>(null);
  const [timerSeed, setTimerSeed] = useState(0);
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [saveError, setSaveError] = useState<string | null>(null);
  const submitCalledRef = useRef(false);

  useEffect(() => {
    document.title = "Assessment In Progress | ARAP";
  }, []);

  const rehydrate = useCallback(async () => {
    if (!state.jwt) return;
    try {
      const data = await apiFetch<SessionData>(`/sessions/${sessionId}`, {
        jwt: state.jwt,
      });
      dispatch({ type: "REHYDRATE", session: data });
      if (data.seconds_remaining !== null) {
        setSecondsLeft(data.seconds_remaining);
        setTimerSeed((s) => s + 1);
      }
    } catch {}
  }, [state.jwt, sessionId, dispatch]);

  useEffect(() => {
    rehydrate();
    window.addEventListener("online", rehydrate);
    return () => window.removeEventListener("online", rehydrate);
  }, [rehydrate]);

  // Client-side countdown
  useEffect(() => {
    if (secondsLeft === null || secondsLeft <= 0) return;
    const id = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(id);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [timerSeed]); // eslint-disable-line react-hooks/exhaustive-deps

  // Rate-limited screen reader announcements: every 60s boundary and when ≤ 60s
  useEffect(() => {
    if (secondsLeft === null) return;
    if (secondsLeft % 60 === 0 || secondsLeft <= 60) {
      setAnnouncedTime(formatTime(secondsLeft));
    }
  }, [secondsLeft]);

  // Auto-submit at expiry
  useEffect(() => {
    if (secondsLeft !== 0 || submitCalledRef.current) return;
    submitCalledRef.current = true;
    handleSubmit();
  }, [secondsLeft]); // eslint-disable-line react-hooks/exhaustive-deps

  const questions = state.session?.questions ?? [];
  const current: Question | undefined = questions[state.currentIndex];

  async function saveAnswer(questionId: string, text: string) {
    if (!state.jwt) return;
    dispatch({ type: "SET_ANSWER", questionId, text });
    setSaving((s) => ({ ...s, [questionId]: true }));
    setSaveError(null);
    try {
      await apiFetch(`/sessions/${sessionId}/questions/${questionId}/answer`, {
        method: "PATCH",
        jwt: state.jwt,
        body: JSON.stringify({ answer_text: text }),
      });
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving((s) => ({ ...s, [questionId]: false }));
    }
  }

  async function handleSubmit() {
    if (!state.jwt || state.submitting) return;
    dispatch({ type: "SET_SUBMITTING", value: true });
    try {
      await apiFetch(`/sessions/${sessionId}/submit`, {
        method: "POST",
        jwt: state.jwt,
      });
      router.push(`/assessment/${sessionId}/done`);
    } catch {
      dispatch({ type: "SET_SUBMITTING", value: false });
    }
  }

  const allAnswered =
    questions.length > 0 && questions.every((q) => !!state.answers[q.id]);
  const timerWarning = secondsLeft !== null && secondsLeft <= 60;

  return (
    <main id="main-content" className="flex min-h-screen flex-col px-6 py-8 max-w-2xl mx-auto">
      {/* Timer */}
      <div className="flex justify-between items-center mb-6">
        <span className="text-sm text-slate-600">
          Question {state.currentIndex + 1} of {questions.length}
        </span>
        {secondsLeft !== null && (
          <>
            {/* Visible countdown — hidden from screen readers */}
            <div
              aria-hidden="true"
              className={`text-sm font-mono font-semibold ${
                timerWarning ? "text-red-600" : "text-slate-700"
              }`}
            >
              {formatTime(secondsLeft)}
            </div>
            {/* Screen-reader live region — announces only at 60s intervals and ≤ 60s */}
            <div aria-live="polite" aria-atomic="true" className="sr-only">
              {announcedTime !== null ? `Time remaining: ${announcedTime}` : ""}
            </div>
          </>
        )}
      </div>

      {/* Question pill nav */}
      <div
        className="flex gap-2 flex-wrap mb-6"
        role="navigation"
        aria-label="Questions"
      >
        {questions.map((q, i) => (
          <button
            key={q.id}
            onClick={() => dispatch({ type: "SET_INDEX", index: i })}
            aria-label={`Question ${i + 1}${state.answers[q.id] ? " (answered)" : ""}`}
            className={`w-8 h-8 rounded-full text-sm font-medium border
              ${state.currentIndex === i ? "bg-slate-900 text-white border-slate-900" : ""}
              ${state.answers[q.id] && state.currentIndex !== i ? "bg-green-100 border-green-400 text-green-800" : ""}
              ${!state.answers[q.id] && state.currentIndex !== i ? "border-slate-300 text-slate-600" : ""}
            `}
          >
            {i + 1}
          </button>
        ))}
      </div>

      {/* Current question */}
      {current && (
        <div className="flex-1 space-y-4">
          <p className="text-slate-900 text-lg font-medium leading-relaxed">
            {current.question.text}
          </p>

          {current.answer_format === "multiple_choice" && current.options && (
            <fieldset className="space-y-2">
              <legend className="sr-only">Select an answer</legend>
              {Object.entries(current.options).map(([key, label]) => (
                <label
                  key={key}
                  className="flex items-center gap-3 p-3 rounded-lg border border-slate-200
                             cursor-pointer hover:border-slate-400
                             has-[:checked]:border-slate-900 has-[:checked]:bg-slate-50"
                >
                  <input
                    type="radio"
                    name={`q-${current.id}`}
                    value={key}
                    checked={state.answers[current.id] === key}
                    onChange={() => saveAnswer(current.id, key)}
                    className="accent-slate-900"
                  />
                  <span className="text-slate-800">{label}</span>
                </label>
              ))}
            </fieldset>
          )}

          {current.answer_format === "short_text" && (
            <div key={current.id}>
              <label htmlFor={`short-${current.id}`} className="sr-only">
                Your answer
              </label>
              <input
                id={`short-${current.id}`}
                type="text"
                defaultValue={state.answers[current.id] ?? ""}
                onBlur={(e) => saveAnswer(current.id, e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900
                           focus:outline focus:outline-2 focus:outline-slate-900"
              />
            </div>
          )}

          {current.answer_format === "long_text" && (
            <div key={current.id}>
              <label htmlFor={`long-${current.id}`} className="sr-only">
                Your answer
              </label>
              <textarea
                id={`long-${current.id}`}
                rows={6}
                defaultValue={state.answers[current.id] ?? ""}
                onBlur={(e) => saveAnswer(current.id, e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900
                           focus:outline focus:outline-2 focus:outline-slate-900 resize-y"
              />
            </div>
          )}

          {/* Fallback for PRD §17 deferred formats (video / voice / code).
              Captures a text answer so scoring continuity is preserved. */}
          {current.answer_format !== "multiple_choice" &&
            current.answer_format !== "short_text" &&
            current.answer_format !== "long_text" && (
              <div key={current.id}>
                <p className="text-sm text-slate-600 mb-2">
                  Please provide your response in text form below.
                </p>
                <label htmlFor={`fallback-${current.id}`} className="sr-only">
                  Your answer
                </label>
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

          {saving[current.id] && (
            <p className="text-xs text-slate-600">Saving&hellip;</p>
          )}
          {saveError && (
            <p role="alert" className="text-xs text-red-600">
              {saveError}
            </p>
          )}
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between items-center mt-8 pt-4 border-t border-slate-100">
        <button
          onClick={() =>
            dispatch({ type: "SET_INDEX", index: state.currentIndex - 1 })
          }
          disabled={state.currentIndex === 0}
          className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm
                     disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Previous
        </button>

        {state.currentIndex < questions.length - 1 ? (
          <button
            onClick={() =>
              dispatch({ type: "SET_INDEX", index: state.currentIndex + 1 })
            }
            className="px-4 py-2 rounded-lg bg-slate-900 text-white text-sm"
          >
            Next
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!allAnswered || state.submitting}
            className="px-6 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {state.submitting ? "Submitting…" : "Submit Assessment"}
          </button>
        )}
      </div>
    </main>
  );
}
```

- [ ] **Step 2: TypeScript + lint check**

```bash
cd apps/candidate-web && npx tsc --noEmit && npm run lint
```

Expected: no errors. The new `AnswerFormat` variants (`video | voice | code`) now satisfy TypeScript since the fallback branch catches them.

- [ ] **Step 3: Commit**

```bash
git add apps/candidate-web/src/app/assessment/[sessionId]/test/page.tsx
git commit -m "[TASK-001] fix(candidate-web): QuestionPage — rate-limited aria-live, contrast, §17 text fallback"
```

---

### Task 5: Done Page — M10-F02 Status Screen

**Files:**
- Modify: `apps/candidate-web/src/app/assessment/[sessionId]/done/page.tsx`

**Interfaces:**
- Consumes: `useSession` → `state.session?.job_title` (null-safe; falls back to "Your Assessment" on refresh)
- Produces: M10-F02 status screen — "Under Review" badge, job title, next-steps copy; no scores, no report data

- [ ] **Step 1: Replace done/page.tsx**

Replace `src/app/assessment/[sessionId]/done/page.tsx` with:

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
    <main
      id="main-content"
      className="flex min-h-screen flex-col items-center justify-center px-6"
    >
      <div className="max-w-md w-full space-y-6">
        <span
          className="inline-flex items-center rounded-full bg-amber-100 px-3 py-1
                     text-sm font-medium text-amber-800"
          aria-label="Status: Under Review"
        >
          Under Review
        </span>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          {jobTitle} — Submitted
        </h1>
        <p className="text-slate-600">
          Thank you for completing your assessment. Your responses are being
          reviewed by the hiring team.
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

- [ ] **Step 2: Full build + lint**

```bash
cd apps/candidate-web && npx tsc --noEmit && npm run lint && npm run build
```

Expected output ends with:
```
Route (app)                              Size     First Load JS
┌ ○ /                                   ...
├ ○ /assessment/[sessionId]             ...
├ ○ /assessment/[sessionId]/consent     ...
├ ○ /assessment/[sessionId]/done        ...
└ ○ /assessment/[sessionId]/test        ...
✓ Compiled successfully
```

No TypeScript errors, no lint warnings, no build failures.

- [ ] **Step 3: Manual browser verification**

Start the dev server:

```bash
cd apps/candidate-web && npm run dev
```

Open `http://localhost:3000`. Tab through the page:
- [ ] Skip link appears on first Tab press and jumps to `#main-content`
- [ ] Page title in browser tab reads "ARAP — Candidate Assessment"

Navigate to a test assessment link (trigger `POST /sessions/{id}/invite` via Swagger at `http://localhost:8000/docs` or use a known token URL):

**Login page** (`/assessment/{id}?token=...`):
- [ ] Browser tab title: "Access Your Assessment | ARAP"
- [ ] Body text is dark enough to read (slate-600, not faded slate-500)
- [ ] Tab focus ring visible on Continue button

**Consent page** (`/assessment/{id}/consent`):
- [ ] Browser tab title: "Assessment Terms | ARAP"
- [ ] Two checkboxes visible; "Start Assessment" button is disabled until both checked
- [ ] Check only T&C — button remains disabled
- [ ] Check only data-processing — button remains disabled
- [ ] Check both — button enables

**Test page** (`/assessment/{id}/test`):
- [ ] Browser tab title: "Assessment In Progress | ARAP"
- [ ] Visible timer counts down every second
- [ ] Using a screen reader (or browser accessibility inspector): confirm the timer live region does NOT fire on every tick — only at 60s boundaries and when ≤ 60s remaining
- [ ] Navigate through questions via pill nav and Prev/Next
- [ ] Answer a question — "Saving…" appears then clears
- [ ] All questions answered → Submit button enables

**Done page** (`/assessment/{id}/done`):
- [ ] Browser tab title: "Submitted | ARAP"
- [ ] "Under Review" amber badge visible
- [ ] Job title appears in heading (if you didn't refresh between submit and done)
- [ ] No score or report data anywhere on the page

- [ ] **Step 4: Commit**

```bash
git add apps/candidate-web/src/app/assessment/[sessionId]/done/page.tsx
git commit -m "[TASK-001] feat(candidate-web): M10-F02 status screen — Under Review badge, job title, next steps"
```

---

## Self-Review

### Spec coverage

| Spec section | Task |
|---|---|
| §3.1 prefers-reduced-motion | Task 1 |
| §3.2 skip link | Task 1 |
| §3.3 AnswerFormat extension | Task 1 |
| §3.4 LoginPage WCAG | Task 2 |
| §3.5 ConsentPage + §15 checkbox | Task 3 |
| §3.6 QuestionPage timer fix + fallback | Task 4 |
| §3.7 Done page M10-F02 | Task 5 |
| WCAG 2.4.1 bypass blocks | Task 1 (skip link) |
| WCAG 2.4.2 page titled | Tasks 2–5 (document.title) |
| WCAG 1.4.3 contrast | Tasks 2–5 (slate-600) |
| WCAG 4.1.3 status messages | Existing role="alert"; timer live region in Task 4 |
| PRD §17 structural readiness | Tasks 1 + 4 |

All spec requirements covered. ✓

### Placeholder scan

No TBDs, no "implement later", no vague steps. All code blocks are complete. ✓

### Type consistency

- `AnswerFormat` extended in Task 1 (`src/lib/types.ts`)
- Task 4 QuestionPage uses the same `AnswerFormat` type via import — the fallback condition matches the three known literal values exactly: `"multiple_choice"`, `"short_text"`, `"long_text"` ✓
- `state.session?.job_title` in Task 5 matches `SessionData.job_title: string` from Task 1 types ✓

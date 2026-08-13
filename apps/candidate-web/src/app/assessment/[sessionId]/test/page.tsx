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
  const [savingAdaptive, setSavingAdaptive] = useState<Record<string, boolean>>({});
  const [adaptiveSaveError, setAdaptiveSaveError] = useState<string | null>(null);
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

  // Announce at minute boundaries and discrete thresholds in the final minute
  const ANNOUNCE_AT = new Set([60, 30, 10, 5, 0]);
  useEffect(() => {
    if (secondsLeft === null) return;
    if (secondsLeft % 60 === 0 || ANNOUNCE_AT.has(secondsLeft)) {
      setAnnouncedTime(formatTime(secondsLeft));
    }
  }, [secondsLeft]); // eslint-disable-line react-hooks/exhaustive-deps

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

  async function saveAdaptiveAnswer(questionId: string, text: string) {
    if (!state.jwt) return;
    dispatch({ type: "SET_ADAPTIVE_ANSWER", questionId, text });
    setSavingAdaptive((s) => ({ ...s, [questionId]: true }));
    setAdaptiveSaveError(null);
    try {
      await apiFetch(`/sessions/${sessionId}/questions/${questionId}/adaptive-answer`, {
        method: "PATCH",
        jwt: state.jwt,
        body: JSON.stringify({ adaptive_answer_text: text }),
      });
    } catch (err: unknown) {
      setAdaptiveSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSavingAdaptive((s) => ({ ...s, [questionId]: false }));
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
    questions.length > 0 &&
    questions.every(
      (q) =>
        !!state.answers[q.id] &&
        (q.answer_format !== "multiple_choice" || !!state.adaptiveAnswers[q.id])
    );
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
        {questions.map((q, i) => {
          const isComplete =
            !!state.answers[q.id] &&
            (q.answer_format !== "multiple_choice" || !!state.adaptiveAnswers[q.id]);
          return (
            <button
              key={q.id}
              onClick={() => dispatch({ type: "SET_INDEX", index: i })}
              aria-label={`Question ${i + 1}${isComplete ? " (answered)" : ""}`}
              className={`w-8 h-8 rounded-full text-sm font-medium border
                ${state.currentIndex === i ? "bg-slate-900 text-white border-slate-900" : ""}
                ${isComplete && state.currentIndex !== i ? "bg-green-100 border-green-400 text-green-800" : ""}
                ${!isComplete && state.currentIndex !== i ? "border-slate-300 text-slate-600" : ""}
              `}
            >
              {i + 1}
            </button>
          );
        })}
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
            <p aria-live="polite" className="text-xs text-slate-600">Saving&hellip;</p>
          )}
          {saveError && (
            <p role="alert" className="text-xs text-red-600">
              {saveError}
            </p>
          )}

          {/* DISC-Based Generative Leadership Question Framework §8 — Natural
              vs Adaptive Behaviour: once a natural (instinctive) answer is
              given, ask which response would be most EFFECTIVE, even if it
              isn't the candidate's natural choice. Required — gates
              submission, same as the natural answer, so the adaptability
              insight in the report always has evidence to draw on. */}
          {current.answer_format === "multiple_choice" &&
            current.options &&
            state.answers[current.id] && (
              <div className="pt-6 mt-6 border-t border-slate-100 space-y-2">
                <p className="text-slate-700 text-sm font-medium">
                  Which response would be most effective — even if it isn&apos;t
                  what you&apos;d naturally do?
                </p>
                <fieldset className="space-y-2">
                  <legend className="sr-only">Select the most effective response</legend>
                  {Object.entries(current.options).map(([key, label]) => (
                    <label
                      key={key}
                      className="flex items-center gap-3 p-3 rounded-lg border border-slate-200
                                 cursor-pointer hover:border-slate-400
                                 has-[:checked]:border-indigo-600 has-[:checked]:bg-indigo-50"
                    >
                      <input
                        type="radio"
                        name={`adaptive-${current.id}`}
                        value={key}
                        checked={state.adaptiveAnswers[current.id] === key}
                        onChange={() => saveAdaptiveAnswer(current.id, key)}
                        className="accent-indigo-600"
                      />
                      <span className="text-slate-800">{label}</span>
                    </label>
                  ))}
                </fieldset>
                {savingAdaptive[current.id] && (
                  <p aria-live="polite" className="text-xs text-slate-600">Saving&hellip;</p>
                )}
                {adaptiveSaveError && (
                  <p role="alert" className="text-xs text-red-600">
                    {adaptiveSaveError}
                  </p>
                )}
              </div>
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

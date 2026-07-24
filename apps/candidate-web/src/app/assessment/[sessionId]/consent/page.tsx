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

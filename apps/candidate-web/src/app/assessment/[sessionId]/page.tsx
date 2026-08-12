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
    <main
      id="main-content"
      className="flex min-h-screen flex-col items-center justify-center px-6
                 bg-gradient-to-br from-slate-50 via-white to-indigo-50"
    >
      <div className="max-w-md w-full animate-fade-in-up">
        <div className="rounded-2xl border border-slate-200 bg-white/80 backdrop-blur-sm shadow-lg shadow-slate-200/50 px-8 py-10 text-center space-y-6">
          <div
            className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl
                       bg-gradient-to-br from-slate-900 to-slate-700 text-white shadow-md"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-7 w-7"
              aria-hidden="true"
            >
              <path d="M9 12l2 2 4-4" />
              <circle cx="12" cy="12" r="9" />
            </svg>
          </div>

          <div className="space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
              Access Your Assessment
            </h1>
            <p className="text-sm text-slate-500">
              Your identity is verified by the secure link in your invitation
              email.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <p role="alert" className="text-sm text-red-600">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-slate-900 px-6 py-3 text-white font-medium
                         transition-colors hover:bg-slate-800
                         disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-slate-900"
            >
              {loading ? "Verifying…" : "Continue"}
            </button>
          </form>
        </div>
      </div>
    </main>
  );
}

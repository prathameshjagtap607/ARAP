"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/context/SessionContext";

export default function LoginPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { dispatch } = useSession();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
    <main className="flex min-h-screen flex-col items-center justify-center px-6">
      <div className="max-w-md w-full space-y-6">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Access Your Assessment
        </h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <p className="text-sm text-slate-500">
            Click continue to access your assessment. Your identity is verified by the secure link in your invitation email.
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

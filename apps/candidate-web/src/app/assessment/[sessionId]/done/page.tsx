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
            className="inline-flex items-center rounded-full bg-amber-100 px-3 py-1 text-sm font-medium text-amber-800"
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

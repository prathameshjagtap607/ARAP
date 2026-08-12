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
      className="flex min-h-screen flex-col items-center justify-center px-6
                 bg-gradient-to-br from-slate-50 via-white to-indigo-50"
    >
      <div className="max-w-md w-full animate-fade-in-up">
        <div className="rounded-2xl border border-slate-200 bg-white/80 backdrop-blur-sm shadow-lg shadow-slate-200/50 px-8 py-10 text-center space-y-6">
          <div
            className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl
                       bg-gradient-to-br from-emerald-600 to-emerald-500 text-white shadow-md"
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

          <span
            className="inline-flex items-center rounded-full bg-amber-100 px-3 py-1 text-sm font-medium text-amber-800"
            role="status"
          >
            Under Review
          </span>

          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            {jobTitle} — Submitted
          </h1>

          <div className="space-y-2">
            <p className="text-slate-600 text-base">
              Thank you for completing your assessment. Your responses are
              being reviewed by the hiring team.
            </p>
            <p className="text-sm text-slate-500">
              You will be contacted with next steps. Results are typically
              reviewed within 2–3 business days.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}

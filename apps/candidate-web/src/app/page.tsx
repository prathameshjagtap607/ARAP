export default function Home() {
  return (
    <main
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
              <path d="M4 4h16v16H4z" opacity="0" />
              <path d="M22 6 12 13 2 6" />
              <path d="M2 6h20v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2Z" />
            </svg>
          </div>

          <div className="space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
              ARAP Candidate Portal
            </h1>
            <p className="text-slate-500 text-base">
              Check your email for your assessment invitation.
            </p>
          </div>

          <button
            disabled
            aria-disabled="true"
            title="Waiting for your invite link"
            className="w-full rounded-lg border border-slate-200 bg-slate-100 px-6 py-3
                       text-slate-400 font-medium cursor-not-allowed"
          >
            Waiting for Invite Link
          </button>
        </div>
      </div>
    </main>
  );
}

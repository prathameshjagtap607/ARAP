export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6">
      <div className="max-w-md w-full text-center space-y-6">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
          ARAP Candidate Portal
        </h1>
        <p className="text-slate-500 text-lg">
          Your assessment link will be emailed to you.
        </p>
        <button
          disabled
          className="w-full rounded-lg bg-slate-900 px-6 py-3 text-white font-medium
                     opacity-40 cursor-not-allowed"
        >
          Access Assessment
        </button>
      </div>
    </main>
  );
}

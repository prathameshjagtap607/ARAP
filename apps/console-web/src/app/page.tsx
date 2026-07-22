const stats = [
  { label: "Active Assessments", value: "—" },
  { label: "Candidates", value: "—" },
  { label: "Reports Generated", value: "—" },
  { label: "Avg. Verdict Time", value: "—" },
];

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-800">Dashboard</h1>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="bg-white rounded-lg border border-slate-200 p-4 space-y-1"
          >
            <p className="text-xs text-slate-500">{stat.label}</p>
            <p className="text-2xl font-semibold text-slate-800">{stat.value}</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-slate-400">
        Console shell — features coming in Phase 1.
      </p>
    </div>
  );
}

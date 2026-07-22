// src/app/(console)/page.tsx
import { SummaryCard } from "@/components/ui/SummaryCard";

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
          <SummaryCard key={stat.label} label={stat.label} value={stat.value} />
        ))}
      </div>
      <p className="text-xs text-slate-400">
        Console shell — features coming in Phase 1.
      </p>
    </div>
  );
}

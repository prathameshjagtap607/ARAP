import { SummaryCard } from "@/components/ui/SummaryCard";

export default function AdminPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-800">Admin</h1>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <SummaryCard label="Organisations" value="—" />
        <SummaryCard label="Total Users" value="—" />
        <SummaryCard label="Active Orgs" value="—" />
      </div>
      <p className="text-xs text-slate-400">
        Organisation & user management — Phase 1.
      </p>
    </div>
  );
}

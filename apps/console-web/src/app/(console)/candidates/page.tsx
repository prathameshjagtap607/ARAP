"use client";

import { useState } from "react";
import { SummaryCard } from "@/components/ui/SummaryCard";
import { FilterBar, type FilterDef } from "@/components/ui/FilterBar";

const filters: FilterDef[] = [
  {
    key: "status",
    label: "Session Status",
    options: [
      { label: "In Progress", value: "in_progress" },
      { label: "Completed", value: "completed" },
      { label: "Pending", value: "pending" },
    ],
  },
];

export default function CandidatesPage() {
  const [search, setSearch] = useState("");
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-800">Candidates & Sessions</h1>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <SummaryCard label="Total Candidates" value="—" />
        <SummaryCard label="Active Sessions" value="—" />
        <SummaryCard label="Completed Today" value="—" />
      </div>
      <FilterBar
        search={search}
        onSearch={setSearch}
        filters={filters}
        values={filterValues}
        onChange={(k, v) => setFilterValues((prev) => ({ ...prev, [k]: v }))}
      />
      <p className="text-xs text-slate-400">Candidate list — Phase 1.</p>
    </div>
  );
}

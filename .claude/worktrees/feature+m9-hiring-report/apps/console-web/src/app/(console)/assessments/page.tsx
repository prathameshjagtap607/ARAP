"use client";

import { useState } from "react";
import { SummaryCard } from "@/components/ui/SummaryCard";
import { FilterBar, type FilterDef } from "@/components/ui/FilterBar";

const filters: FilterDef[] = [
  {
    key: "status",
    label: "Status",
    options: [
      { label: "Active", value: "active" },
      { label: "Draft", value: "draft" },
      { label: "Closed", value: "closed" },
    ],
  },
];

export default function AssessmentsPage() {
  const [search, setSearch] = useState("");
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-800">Job Assessments</h1>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <SummaryCard label="Total Assessments" value="—" />
        <SummaryCard label="Active" value="—" />
        <SummaryCard label="Avg. Completion Rate" value="—" />
      </div>
      <FilterBar
        search={search}
        onSearch={setSearch}
        filters={filters}
        values={filterValues}
        onChange={(k, v) => setFilterValues((prev) => ({ ...prev, [k]: v }))}
      />
      <p className="text-xs text-slate-400">Assessment list — Phase 1.</p>
    </div>
  );
}

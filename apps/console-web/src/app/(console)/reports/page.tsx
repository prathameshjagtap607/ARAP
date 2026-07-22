"use client";

import { useState } from "react";
import { FilterBar, type FilterDef } from "@/components/ui/FilterBar";
import { ReportCard } from "@/components/ui/ReportCard";

const filters: FilterDef[] = [
  {
    key: "type",
    label: "Report Type",
    options: [
      { label: "Assessment", value: "assessment" },
      { label: "Candidate", value: "candidate" },
    ],
  },
];

const placeholderReports = [
  { title: "Weekly Assessment Summary", meta: "Generated — · PDF" },
  { title: "Candidate Pipeline Report", meta: "Generated — · PDF" },
  { title: "Score Distribution Analysis", meta: "Generated — · PDF" },
];

export default function ReportsPage() {
  const [search, setSearch] = useState("");
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-800">Reports</h1>
      <FilterBar
        search={search}
        onSearch={setSearch}
        filters={filters}
        values={filterValues}
        onChange={(k, v) => setFilterValues((prev) => ({ ...prev, [k]: v }))}
      />
      <div className="space-y-2">
        {placeholderReports.map((r) => (
          <ReportCard key={r.title} title={r.title} meta={r.meta} />
        ))}
      </div>
    </div>
  );
}

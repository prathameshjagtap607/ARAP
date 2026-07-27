"use client";

import { SummaryCard } from "@/components/ui/SummaryCard";
import { ChartCard } from "@/components/ui/ChartCard";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const placeholderData = [
  { name: "Mon", count: 0 },
  { name: "Tue", count: 0 },
  { name: "Wed", count: 0 },
  { name: "Thu", count: 0 },
  { name: "Fri", count: 0 },
];

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-800">Analytics</h1>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <SummaryCard label="Sessions This Week" value="—" />
        <SummaryCard label="Pass Rate" value="—" />
        <SummaryCard label="Avg. Score" value="—" />
      </div>
      <ChartCard title="Sessions by Day (placeholder)">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={placeholderData}>
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="count" fill="#475569" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  );
}

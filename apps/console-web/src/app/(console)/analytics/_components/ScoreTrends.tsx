"use client";

import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { fetchScoreTrends } from "../_lib/api";
import type { ScoreTrendPoint, AnalyticsFilters } from "../_lib/types";

const COLORS = ["#3b82f6","#ef4444","#10b981","#f59e0b","#8b5cf6","#ec4899"];

export default function ScoreTrends() {
  const [data, setData] = useState<ScoreTrendPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCompetencies, setShowCompetencies] = useState(false);
  const [filters, setFilters] = useState<AnalyticsFilters>({ granularity: "week" });

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchScoreTrends(filters, controller.signal)
      .then((res) => { if (!controller.signal.aborted) setData(res.data); })
      .catch((err) => { if (err?.name !== "AbortError") setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [filters]);

  const competencyKeys = data.length > 0
    ? Object.keys(data[0].avg_by_competency)
    : [];

  const chartData = data.map((point) => ({
    period: new Date(point.period).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    "Overall": Number(point.avg_overall.toFixed(2)),
    ...Object.fromEntries(
      Object.entries(point.avg_by_competency).map(([k, v]) => [k, Number(v.toFixed(2))])
    ),
  }));

  if (loading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-6 animate-pulse">
        <div className="h-6 bg-slate-200 rounded w-40 mb-4" />
        <div className="h-64 bg-slate-100 rounded" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-white p-6 text-red-600 text-sm">
        Failed to load score trends: {error}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex gap-3 items-center">
          <select
            className="text-sm border border-slate-200 rounded px-2 py-1"
            value={filters.granularity}
            onChange={(e) => setFilters((f) => ({ ...f, granularity: e.target.value as "week" | "month" }))}
          >
            <option value="week">Weekly</option>
            <option value="month">Monthly</option>
          </select>
          <button
            className="text-sm text-slate-600 underline"
            onClick={() => setShowCompetencies((v) => !v)}
          >
            {showCompetencies ? "Hide competencies" : "Show per-competency"}
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Score Trends</h3>
        {data.length === 0 ? (
          <div className="text-slate-500 text-sm py-12 text-center">No data available for the selected filters</div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="period" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 5]} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="Overall" stroke={COLORS[0]} strokeWidth={2} dot={false} />
              {showCompetencies && competencyKeys.map((key, i) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={COLORS[(i + 1) % COLORS.length]}
                  strokeWidth={1}
                  strokeDasharray="4 2"
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

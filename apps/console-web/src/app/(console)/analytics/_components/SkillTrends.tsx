"use client";

import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { fetchSkillTrends } from "../_lib/api";
import type { SkillTrendPoint } from "../_lib/types";

const COLORS = ["#3b82f6","#ef4444","#10b981","#f59e0b","#8b5cf6","#ec4899"];

export default function SkillTrends() {
  const [data, setData] = useState<SkillTrendPoint[]>([]);
  const [hasData, setHasData] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchSkillTrends({}, controller.signal)
      .then((res) => {
        if (!controller.signal.aborted) {
          setData(res.data);
          setHasData(res.has_data);
        }
      })
      .catch((err) => { if (err?.name !== "AbortError") setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

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
        Failed to load skill trends: {error}
      </div>
    );
  }

  if (!hasData) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-2">Skill Trends</h3>
        <div className="text-slate-500 text-sm py-12 text-center">
          <p className="font-medium">No trend data yet</p>
          <p className="mt-1 text-slate-400">Skill trend snapshots are collected weekly. Check back after assessments have run.</p>
        </div>
      </div>
    );
  }

  // Pivot: [{week_start, competency1: avg, competency2: avg, ...}]
  const weeks = Array.from(new Set(data.map((d) => d.week_start))).sort();
  const competencies = Array.from(new Set(data.map((d) => d.competency)));
  const chartData = weeks.map((week) => {
    const entry: Record<string, string | number> = { week };
    data.filter((d) => d.week_start === week).forEach((d) => {
      entry[d.competency] = d.avg_score;
    });
    return entry;
  });

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6">
      <h3 className="text-lg font-semibold text-slate-900 mb-4">Skill Trends</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="week" tick={{ fontSize: 11 }} />
          <YAxis domain={[0, 5]} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          {competencies.map((comp, i) => (
            <Line
              key={comp}
              type="monotone"
              dataKey={comp}
              stroke={COLORS[i % COLORS.length]}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

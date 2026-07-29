"use client";

import { useEffect, useState } from "react";
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { fetchQuestionAnalytics } from "../_lib/api";
import type { QuestionCategoryRow } from "../_lib/types";

const COLORS = ["#3b82f6","#ef4444","#10b981","#f59e0b","#8b5cf6","#ec4899"];

export default function QuestionAnalytics() {
  const [rows, setRows] = useState<QuestionCategoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchQuestionAnalytics({}, controller.signal)
      .then((res) => { if (!controller.signal.aborted) setRows(res.rows); })
      .catch((err) => { if (err?.name !== "AbortError") setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  // Category counts for pie chart
  const categoryCounts = Array.from(
    rows.reduce((acc, r) => {
      acc.set(r.category, (acc.get(r.category) || 0) + r.question_count);
      return acc;
    }, new Map<string, number>())
  ).map(([name, value]) => ({ name, value }));

  // Difficulty distribution for bar chart
  const difficultyData = Array.from(
    rows.reduce((acc, r) => {
      acc.set(r.difficulty, (acc.get(r.difficulty) || 0) + r.question_count);
      return acc;
    }, new Map<string, number>())
  ).map(([name, count]) => ({ name, count }));

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
        Failed to load question analytics: {error}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-6 text-slate-500 text-sm text-center py-12">
        No question data available
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Category Distribution</h3>
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie dataKey="value" nameKey="name" data={categoryCounts} cx="50%" cy="50%" label>
              {categoryCounts.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Difficulty Distribution</h3>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={difficultyData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="count" fill="#3b82f6" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

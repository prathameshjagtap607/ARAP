"use client";

import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { fetchFunnel } from "../_lib/api";
import type { FunnelRow } from "../_lib/types";

export default function HiringFunnel() {
  const [rows, setRows] = useState<FunnelRow[]>([]);
  const [totals, setTotals] = useState<FunnelRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchFunnel({}, controller.signal)
      .then((res) => {
        if (!controller.signal.aborted) {
          setRows(res.rows);
          setTotals(res.totals);
        }
      })
      .catch((err) => { if (err?.name !== "AbortError") setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  const chartData = rows.map((r) => ({
    name: `${r.role} / ${r.department}`,
    Invited: r.total_invited,
    Completed: r.completed,
    Hired: r.hired,
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
        Failed to load funnel: {error}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {totals && (
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-lg border border-slate-200 bg-white p-4 text-center">
            <div className="text-2xl font-bold text-slate-900">{totals.total_invited}</div>
            <div className="text-sm text-slate-500 mt-1">Total Invited</div>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4 text-center">
            <div className="text-2xl font-bold text-slate-900">{totals.completed}</div>
            <div className="text-sm text-slate-500 mt-1">
              Completed ({totals.total_invited > 0 ? Math.round(totals.completion_rate * 100) : 0}%)
            </div>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4 text-center">
            <div className="text-2xl font-bold text-green-700">{totals.hired}</div>
            <div className="text-sm text-slate-500 mt-1">
              Hired ({totals.completed > 0 ? Math.round(totals.hire_rate * 100) : 0}%)
            </div>
          </div>
        </div>
      )}

      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Hiring Funnel by Role</h3>
        {rows.length === 0 ? (
          <div className="text-slate-500 text-sm py-12 text-center">No data available</div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis dataKey="name" type="category" width={160} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="Invited" fill="#3b82f6" />
              <Bar dataKey="Completed" fill="#10b981" />
              <Bar dataKey="Hired" fill="#f59e0b" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

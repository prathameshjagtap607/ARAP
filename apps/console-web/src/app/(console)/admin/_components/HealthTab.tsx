"use client";

import { useEffect, useState } from "react";
import { fetchHealthOverview, fetchIncidents, fetchFraudFlags } from "../_lib/api";
import type { FraudFlagStats, HealthOverview, IncidentEntry } from "../_lib/types";

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 text-center">
      <div className="text-2xl font-bold text-slate-900">{value}</div>
      <div className="text-sm text-slate-500 mt-1">{label}</div>
    </div>
  );
}

function fmt(v: number | null): string {
  return v == null ? "—" : `${v.toFixed(1)}s`;
}

export default function HealthTab() {
  const [overview, setOverview] = useState<HealthOverview | null>(null);
  const [incidents, setIncidents] = useState<IncidentEntry[]>([]);
  const [fraud, setFraud] = useState<FraudFlagStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    Promise.all([
      fetchHealthOverview(controller.signal),
      fetchIncidents(controller.signal),
      fetchFraudFlags(controller.signal),
    ])
      .then(([ov, inc, fr]) => {
        if (!controller.signal.aborted) {
          setOverview(ov);
          setIncidents(inc);
          setFraud(fr);
        }
      })
      .catch((err) => { if (err?.name !== "AbortError") setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  if (loading) return <div className="animate-pulse h-40 bg-slate-100 rounded-lg" />;
  if (error) return <div className="text-red-600 text-sm p-4 border border-red-200 rounded-lg">Failed to load health data: {error}</div>;

  return (
    <div className="space-y-6">
      {overview && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <StatTile label="Queue Depth" value={overview.queue_depth} />
          <StatTile label="Error Rate (24h)" value={`${(overview.error_rate_24h * 100).toFixed(1)}%`} />
          <StatTile label="Sessions (24h)" value={overview.total_sessions_24h} />
          <StatTile label="p50 Latency" value={fmt(overview.p50_seconds)} />
          <StatTile label="p95 Latency" value={fmt(overview.p95_seconds)} />
          <StatTile label="p99 Latency" value={fmt(overview.p99_seconds)} />
        </div>
      )}

      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <h3 className="text-sm font-semibold text-slate-700 mb-4">Incidents (Last 7 Days)</h3>
        {incidents.length === 0 ? (
          <p className="text-slate-400 text-sm text-center py-4">No incidents</p>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="text-slate-500 text-left"><th className="pb-2">Status</th><th className="pb-2">Count</th><th className="pb-2">Last Seen</th></tr></thead>
            <tbody>{incidents.map((i) => (
              <tr key={i.status} className="border-t border-slate-100">
                <td className="py-2 font-mono text-red-600">{i.status}</td>
                <td className="py-2">{i.count}</td>
                <td className="py-2 text-slate-500">{i.last_seen ?? "—"}</td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </div>

      {fraud && (
        <div className="rounded-lg border border-slate-200 bg-white p-6">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Fraud Flag Summary</h3>
          <div className="grid grid-cols-3 gap-4">
            <StatTile label="Total Flags" value={fraud.total_flags} />
            <StatTile label="False Positives" value={fraud.false_positive_count} />
            <StatTile label="False Positive Rate" value={`${(fraud.false_positive_rate * 100).toFixed(1)}%`} />
          </div>
        </div>
      )}
    </div>
  );
}

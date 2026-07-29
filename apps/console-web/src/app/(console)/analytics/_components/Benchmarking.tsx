"use client";

import { useState } from "react";
import { fetchBenchmark } from "../_lib/api";
import type { BenchmarkResponse } from "../_lib/types";

export default function Benchmarking() {
  const [sessionId, setSessionId] = useState("");
  const [result, setResult] = useState<BenchmarkResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!sessionId.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetchBenchmark(sessionId.trim());
      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const percentilePct = result ? Math.round(result.percentile * 100) : 0;

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Candidate Benchmarking</h3>
        <div className="flex gap-3">
          <input
            type="text"
            placeholder="Paste session ID (UUID)..."
            className="flex-1 border border-slate-200 rounded px-3 py-2 text-sm"
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <button
            onClick={handleSearch}
            disabled={loading}
            className="px-4 py-2 bg-slate-800 text-white rounded text-sm disabled:opacity-50"
          >
            {loading ? "Loading..." : "Look up"}
          </button>
        </div>

        {error && (
          <div className="mt-4 text-red-600 text-sm">{error}</div>
        )}

        {result && (
          <div className="mt-6 space-y-4">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="rounded border border-slate-200 p-4 text-center">
                <div className="text-2xl font-bold text-slate-900">{result.overall_score.toFixed(2)}</div>
                <div className="text-xs text-slate-500 mt-1">Overall Score</div>
              </div>
              <div className="rounded border border-slate-200 p-4 text-center">
                <div className="text-2xl font-bold text-blue-600">{percentilePct}th</div>
                <div className="text-xs text-slate-500 mt-1">Percentile</div>
              </div>
              <div className="rounded border border-slate-200 p-4 text-center">
                <div className="text-2xl font-bold text-slate-900">{result.peer_count}</div>
                <div className="text-xs text-slate-500 mt-1">Peers Assessed</div>
              </div>
              <div className="rounded border border-slate-200 p-4 text-center">
                <div className="text-sm font-medium text-slate-700">
                  P25: {result.p25.toFixed(2)} / P50: {result.p50.toFixed(2)} / P75: {result.p75.toFixed(2)}
                </div>
                <div className="text-xs text-slate-500 mt-1">Quartile Benchmarks</div>
              </div>
            </div>

            {/* Percentile bar */}
            <div className="space-y-1">
              <div className="text-xs text-slate-500">Percentile rank among peers</div>
              <div className="relative h-4 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="absolute left-0 top-0 h-full bg-blue-500 rounded-full transition-all"
                  style={{ width: `${percentilePct}%` }}
                />
                <div
                  className="absolute top-0 h-full w-0.5 bg-slate-400"
                  style={{ left: `${Math.round((result.p25 / 5) * 100)}%` }}
                  title={`P25: ${result.p25.toFixed(2)}`}
                />
                <div
                  className="absolute top-0 h-full w-0.5 bg-slate-600"
                  style={{ left: `${Math.round((result.p50 / 5) * 100)}%` }}
                  title={`Median: ${result.p50.toFixed(2)}`}
                />
                <div
                  className="absolute top-0 h-full w-0.5 bg-slate-400"
                  style={{ left: `${Math.round((result.p75 / 5) * 100)}%` }}
                  title={`P75: ${result.p75.toFixed(2)}`}
                />
              </div>
              <div className="flex justify-between text-xs text-slate-400">
                <span>0</span><span>5.0</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

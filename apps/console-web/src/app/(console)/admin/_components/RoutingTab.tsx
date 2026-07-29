"use client";

import { useEffect, useState } from "react";
import { fetchRoutingConfigs, updateRoutingConfig } from "../_lib/api";
import type { ModelRoutingConfig } from "../_lib/types";

export default function RoutingTab() {
  const [configs, setConfigs] = useState<ModelRoutingConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Record<string, Partial<ModelRoutingConfig>>>({});

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchRoutingConfigs(controller.signal)
      .then((data) => { if (!controller.signal.aborted) setConfigs(data); })
      .catch((err) => { if (err?.name !== "AbortError") setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  async function handleSave(agentName: string) {
    const patch = editing[agentName];
    if (!patch) return;
    const updated = await updateRoutingConfig(agentName, patch);
    setConfigs((prev) => prev.map((c) => (c.agent_name === agentName ? updated : c)));
    setEditing((prev) => { const next = { ...prev }; delete next[agentName]; return next; });
  }

  if (loading) return <div className="animate-pulse h-40 bg-slate-100 rounded-lg" />;
  if (error) return <div className="text-red-600 text-sm p-4 border border-red-200 rounded-lg">Failed to load routing config: {error}</div>;

  return (
    <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            <th className="px-4 py-3 text-left font-medium">Agent</th>
            <th className="px-4 py-3 text-left font-medium">Provider</th>
            <th className="px-4 py-3 text-left font-medium">Model</th>
            <th className="px-4 py-3 text-left font-medium">Fallback Model</th>
            <th className="px-4 py-3 text-right font-medium">Last Updated</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {configs.map((c) => {
            const edit = editing[c.agent_name] ?? {};
            return (
              <tr key={c.agent_name} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-slate-700">{c.agent_name}</td>
                <td className="px-4 py-3">
                  <input
                    className="border border-slate-300 rounded px-2 py-1 text-sm w-28"
                    value={edit.provider ?? c.provider}
                    onChange={(e) => setEditing((prev) => ({ ...prev, [c.agent_name]: { ...prev[c.agent_name], provider: e.target.value } }))}
                  />
                </td>
                <td className="px-4 py-3">
                  <input
                    className="border border-slate-300 rounded px-2 py-1 text-sm w-48"
                    value={edit.model_id ?? c.model_id}
                    onChange={(e) => setEditing((prev) => ({ ...prev, [c.agent_name]: { ...prev[c.agent_name], model_id: e.target.value } }))}
                  />
                </td>
                <td className="px-4 py-3">
                  <input
                    className="border border-slate-300 rounded px-2 py-1 text-sm w-48"
                    placeholder="none"
                    value={edit.fallback_model_id ?? c.fallback_model_id ?? ""}
                    onChange={(e) => setEditing((prev) => ({ ...prev, [c.agent_name]: { ...prev[c.agent_name], fallback_model_id: e.target.value || null } }))}
                  />
                </td>
                <td className="px-4 py-3 text-right text-slate-500">{new Date(c.updated_at).toLocaleDateString()}</td>
                <td className="px-4 py-3 text-right">
                  {editing[c.agent_name] && (
                    <button onClick={() => handleSave(c.agent_name)} className="text-xs text-blue-600 hover:underline">Save</button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="px-4 py-2 text-xs text-slate-400 border-t border-slate-100">Changes take effect within 30s — no redeploy needed.</p>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { fetchPrompts, activatePrompt, rollbackPrompt } from "../_lib/api";
import type { PromptVersion } from "../_lib/types";

export default function PromptsTab() {
  const [templates, setTemplates] = useState<PromptVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchPrompts(controller.signal)
      .then((data) => { if (!controller.signal.aborted) setTemplates(data); })
      .catch((err) => { if (err?.name !== "AbortError") setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  async function handleActivate(id: string) {
    const updated = await activatePrompt(id);
    setTemplates((prev) =>
      prev.map((t) =>
        t.agent_name === updated.agent_name && t.org_id === updated.org_id
          ? { ...t, is_active: t.id === updated.id }
          : t
      )
    );
  }

  async function handleRollback(id: string) {
    const updated = await rollbackPrompt(id);
    setTemplates((prev) =>
      prev.map((t) =>
        t.agent_name === updated.agent_name && t.org_id === updated.org_id
          ? { ...t, is_active: t.id === updated.id }
          : t
      )
    );
  }

  if (loading) return <div className="animate-pulse h-40 bg-slate-100 rounded-lg" />;
  if (error) return <div className="text-red-600 text-sm p-4 border border-red-200 rounded-lg">Failed to load prompts: {error}</div>;

  const grouped = templates.reduce<Record<string, PromptVersion[]>>((acc, t) => {
    (acc[t.agent_name] ??= []).push(t);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([agentName, versions]) => (
        <div key={agentName} className="rounded-lg border border-slate-200 bg-white overflow-hidden">
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-200">
            <h3 className="text-sm font-semibold text-slate-700">{agentName}</h3>
          </div>
          <table className="w-full text-sm">
            <thead className="text-slate-500">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Version</th>
                <th className="px-4 py-2 text-left font-medium">Created</th>
                <th className="px-4 py-2 text-left font-medium">Status</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {versions.map((v) => (
                <tr key={v.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2 font-mono text-slate-700">{v.version}</td>
                  <td className="px-4 py-2 text-slate-500">{new Date(v.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-2">
                    {v.is_active && (
                      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700">Active</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right space-x-3">
                    {!v.is_active && (
                      <button onClick={() => handleActivate(v.id)} className="text-xs text-blue-600 hover:underline">Activate</button>
                    )}
                    {v.is_active && (
                      <button onClick={() => handleRollback(v.id)} className="text-xs text-amber-600 hover:underline">Rollback</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
      {templates.length === 0 && (
        <div className="text-slate-400 text-sm text-center py-12">No prompt templates yet</div>
      )}
    </div>
  );
}

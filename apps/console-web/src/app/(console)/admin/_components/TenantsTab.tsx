"use client";

import { useEffect, useState } from "react";
import { fetchTenants, suspendTenant } from "../_lib/api";
import type { TenantDetail } from "../_lib/types";

export default function TenantsTab() {
  const [tenants, setTenants] = useState<TenantDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchTenants(controller.signal)
      .then((data) => { if (!controller.signal.aborted) setTenants(data); })
      .catch((err) => { if (err?.name !== "AbortError") setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  async function handleSuspend(orgId: string) {
    const updated = await suspendTenant(orgId);
    setTenants((prev) => prev.map((t) => (t.id === orgId ? updated : t)));
  }

  if (loading) {
    return <div className="animate-pulse h-40 bg-slate-100 rounded-lg" />;
  }
  if (error) {
    return <div className="text-red-600 text-sm p-4 border border-red-200 rounded-lg">Failed to load tenants: {error}</div>;
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            <th className="px-4 py-3 text-left font-medium">Name</th>
            <th className="px-4 py-3 text-left font-medium">Plan</th>
            <th className="px-4 py-3 text-right font-medium">Users</th>
            <th className="px-4 py-3 text-right font-medium">Sessions</th>
            <th className="px-4 py-3 text-left font-medium">Status</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tenants.map((t) => (
            <tr key={t.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 font-medium text-slate-800">{t.name}</td>
              <td className="px-4 py-3 text-slate-600">{t.plan_tier}</td>
              <td className="px-4 py-3 text-right text-slate-600">{t.user_count}</td>
              <td className="px-4 py-3 text-right text-slate-600">{t.session_count}</td>
              <td className="px-4 py-3">
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${t.is_active ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                  {t.is_active ? "Active" : "Suspended"}
                </span>
              </td>
              <td className="px-4 py-3 text-right">
                {t.is_active && (
                  <button
                    onClick={() => handleSuspend(t.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Suspend
                  </button>
                )}
              </td>
            </tr>
          ))}
          {tenants.length === 0 && (
            <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400 text-sm">No tenants found</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

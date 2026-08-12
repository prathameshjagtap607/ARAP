'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import SummaryCard from '@/components/dashboard/SummaryCard';
import { fetchAdminDashboard } from '@/lib/api/dashboards';
import type { AdminDashboardData } from '@/lib/types/dashboard';

export default function AdminDashboardPage() {
  const { user } = useAuth();
  const orgId = user?.orgId || '';

  // State for dashboard data
  const [data, setData] = useState<AdminDashboardData>({
    totalUsers: 0,
    competencyCount: 0,
    templateCount: 0,
    users: [],
    competencies: [],
    templates: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Abort controller for cleanup
  const [abortController, setAbortController] = useState<AbortController | null>(null);

  // Fetch dashboard data on mount and when org changes
  useEffect(() => {
    if (!orgId) return;

    const controller = new AbortController();
    setAbortController(controller);

    const loadDashboard = async () => {
      setLoading(true);
      setError(null);
      try {
        const dashboardData = await fetchAdminDashboard(orgId, controller.signal);
        if (!controller.signal.aborted) {
          setData(dashboardData);
        }
      } catch (err) {
        if (err instanceof Error && err.name !== 'AbortError') {
          console.error('Failed to load admin dashboard:', err);
          setError('Failed to load dashboard data');
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    loadDashboard();

    return () => {
      controller.abort();
    };
  }, [orgId]);

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '—';
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return dateString;
    }
  };

  const getRoleBadgeColor = (role: string): 'amber' | 'green' | 'blue' | 'red' => {
    return role === 'admin' ? 'green' : 'blue';
  };

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <h1 className="text-2xl font-bold text-slate-900">Admin Dashboard</h1>

      {/* Error Alert */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm font-medium text-red-900">{error}</p>
        </div>
      )}

      {/* Summary Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SummaryCard
          title="Total Users"
          value={data.totalUsers}
          icon="👥"
          loading={loading}
        />
        <SummaryCard
          title="Competency Entries"
          value={data.competencyCount}
          icon="🎯"
          loading={loading}
        />
        <SummaryCard
          title="Role Templates"
          value={data.templateCount}
          icon="📋"
          loading={loading}
        />
      </div>

      {/* Users Table */}
      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">Users</h2>
        </div>

        {loading ? (
          <div className="px-6 py-12 text-center">
            <div className="inline-block">
              <div className="animate-pulse space-y-4">
                <div className="h-12 bg-slate-200 rounded w-96"></div>
                <div className="h-12 bg-slate-200 rounded w-96"></div>
                <div className="h-12 bg-slate-200 rounded w-96"></div>
              </div>
            </div>
          </div>
        ) : data.users.length === 0 ? (
          <div className="px-6 py-12 text-center text-slate-500">
            <p>No users found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">
                    Name
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">
                    Email
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">
                    Role
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">
                    Joined Date
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.users.map((user) => (
                  <tr
                    key={user.id}
                    className="border-b border-slate-200 hover:bg-slate-50 transition-colors"
                  >
                    <td className="px-6 py-4 text-slate-900 font-medium">
                      {user.name}
                    </td>
                    <td className="px-6 py-4 text-slate-700">
                      {user.email}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${
                          getRoleBadgeColor(user.role) === 'green'
                            ? 'bg-green-100 text-green-900'
                            : 'bg-blue-100 text-blue-900'
                        }`}
                      >
                        {user.role.charAt(0).toUpperCase() + user.role.slice(1)}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-700">
                      {formatDate(user.createdAt)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Competencies Table */}
      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">Competencies</h2>
        </div>

        {loading ? (
          <div className="px-6 py-12 text-center">
            <div className="inline-block">
              <div className="animate-pulse space-y-4">
                <div className="h-12 bg-slate-200 rounded w-96"></div>
                <div className="h-12 bg-slate-200 rounded w-96"></div>
                <div className="h-12 bg-slate-200 rounded w-96"></div>
              </div>
            </div>
          </div>
        ) : data.competencies.length === 0 ? (
          <div className="px-6 py-12 text-center text-slate-500">
            <p>No competencies found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">
                    Name
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">
                    Category
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">
                    Entry Count
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">
                    Created Date
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.competencies.map((competency) => (
                  <tr
                    key={competency.id}
                    className="border-b border-slate-200 hover:bg-slate-50 transition-colors"
                  >
                    <td className="px-6 py-4 text-slate-900 font-medium">
                      {competency.name}
                    </td>
                    <td className="px-6 py-4 text-slate-700">
                      {competency.category}
                    </td>
                    <td className="px-6 py-4 text-slate-700">
                      {competency.entryCount}
                    </td>
                    <td className="px-6 py-4 text-slate-700">
                      {formatDate(competency.createdAt)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Templates Table */}
      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">Role Templates</h2>
        </div>

        {loading ? (
          <div className="px-6 py-12 text-center">
            <div className="inline-block">
              <div className="animate-pulse space-y-4">
                <div className="h-12 bg-slate-200 rounded w-96"></div>
                <div className="h-12 bg-slate-200 rounded w-96"></div>
                <div className="h-12 bg-slate-200 rounded w-96"></div>
              </div>
            </div>
          </div>
        ) : data.templates.length === 0 ? (
          <div className="px-6 py-12 text-center text-slate-500">
            <p>No role templates found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">
                    Name
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">
                    Created Date
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.templates.map((template) => (
                  <tr
                    key={template.id}
                    className="border-b border-slate-200 hover:bg-slate-50 transition-colors"
                  >
                    <td className="px-6 py-4 text-slate-900 font-medium">
                      {template.name}
                    </td>
                    <td className="px-6 py-4 text-slate-700">
                      {formatDate(template.createdAt)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import SummaryCard from '@/components/dashboard/SummaryCard';
import FilterBar from '@/components/dashboard/FilterBar';
import { fetchHRDashboardCounts, fetchRecentSessions, fetchUsersList } from '@/lib/api/dashboards';
import type { Filter } from '@/lib/types/dashboard';
import type { DashboardSession } from '@/lib/types/dashboard';

const statusBadgeMap: Record<string, { color: 'amber' | 'green' | 'red' | 'blue' }> = {
  invited: { color: 'amber' },
  in_progress: { color: 'blue' },
  completed: { color: 'green' },
  expired: { color: 'red' },
};

export default function HRDashboardPage() {
  const { user } = useAuth();
  const orgId = user?.orgId || '';
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';

  // State for counts/summary data
  const [counts, setCounts] = useState({
    activeAssessments: 0,
    candidatesInProgress: 0,
    awaitingReview: 0,
    pendingDecisions: 0,
  });
  const [countsLoading, setCountsLoading] = useState(true);

  // State for recent sessions
  const [sessions, setSessions] = useState<DashboardSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);

  // State for filter
  const [statusFilter, setStatusFilter] = useState('');
  const [filterUserId, setFilterUserId] = useState('');
  const [userOptions, setUserOptions] = useState<{ label: string; value: string }[]>([]);

  // Abort controller for cleanup
  const [abortController, setAbortController] = useState<AbortController | null>(null);

  // Admin-only: load the user list to populate the "Filter by user" dropdown
  useEffect(() => {
    if (!isAdmin) return;
    fetchUsersList().then((users) => {
      setUserOptions(users.map((u) => ({ label: u.email, value: u.id })));
    });
  }, [isAdmin]);

  const filters: Filter[] = [
    {
      key: 'status',
      label: 'Session Status',
      type: 'select',
      placeholder: 'All Statuses',
      options: [
        { label: 'Invited', value: 'invited' },
        { label: 'In Progress', value: 'in_progress' },
        { label: 'Completed', value: 'completed' },
        { label: 'Expired', value: 'expired' },
      ],
    },
    ...(isAdmin
      ? [
          {
            key: 'filterUserId',
            label: 'Filter by User',
            type: 'select' as const,
            placeholder: 'All Users',
            options: userOptions,
          },
        ]
      : []),
  ];

  // Fetch counts on mount and when org changes
  useEffect(() => {
    if (!orgId) return;

    const controller = new AbortController();
    setAbortController(controller);

    const loadCounts = async () => {
      setCountsLoading(true);
      try {
        const data = await fetchHRDashboardCounts(orgId, controller.signal, filterUserId || undefined);
        if (!controller.signal.aborted) {
          setCounts(data);
        }
      } catch (error) {
        if (error instanceof Error && error.name !== 'AbortError') {
          console.error('Failed to load counts:', error);
        }
      } finally {
        if (!controller.signal.aborted) {
          setCountsLoading(false);
        }
      }
    };

    loadCounts();

    return () => {
      controller.abort();
    };
  }, [orgId, filterUserId]);

  // Fetch sessions on mount and when status filter changes
  useEffect(() => {
    if (!orgId) return;

    const controller = new AbortController();
    setAbortController(controller);

    const loadSessions = async () => {
      setSessionsLoading(true);
      try {
        const data = await fetchRecentSessions(
          orgId,
          statusFilter || undefined,
          20,
          controller.signal,
          filterUserId || undefined
        );
        if (!controller.signal.aborted) {
          setSessions(data);
        }
      } catch (error) {
        if (error instanceof Error && error.name !== 'AbortError') {
          console.error('Failed to load sessions:', error);
        }
      } finally {
        if (!controller.signal.aborted) {
          setSessionsLoading(false);
        }
      }
    };

    loadSessions();

    return () => {
      controller.abort();
    };
  }, [orgId, statusFilter, filterUserId]);

  const handleFilterApply = (values: Record<string, any>) => {
    setStatusFilter(values.status || '');
    setFilterUserId(values.filterUserId || '');
  };

  const handleFilterReset = () => {
    setStatusFilter('');
    setFilterUserId('');
  };

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

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <h1 className="text-2xl font-bold text-slate-900">HR Dashboard</h1>

      {/* Summary Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard
          title="Active Assessments"
          value={counts.activeAssessments}
          icon="📋"
          loading={countsLoading}
        />
        <SummaryCard
          title="Candidates In Progress"
          value={counts.candidatesInProgress}
          icon="👥"
          loading={countsLoading}
        />
        <SummaryCard
          title="Awaiting Review"
          value={counts.awaitingReview}
          icon="🔍"
          loading={countsLoading}
        />
        <SummaryCard
          title="Pending Final Decision"
          value={counts.pendingDecisions}
          icon="⏳"
          loading={countsLoading}
        />
      </div>

      {/* Filter Bar */}
      <FilterBar
        filters={filters}
        onApply={handleFilterApply}
        onReset={handleFilterReset}
        loading={sessionsLoading}
      />

      {/* Recent Sessions Table */}
      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">Recent Sessions</h2>
        </div>

        {sessionsLoading ? (
          <div className="px-6 py-12 text-center">
            <div className="inline-block">
              <div className="animate-pulse space-y-4">
                <div className="h-12 bg-slate-200 rounded w-96"></div>
                <div className="h-12 bg-slate-200 rounded w-96"></div>
                <div className="h-12 bg-slate-200 rounded w-96"></div>
              </div>
            </div>
          </div>
        ) : sessions.length === 0 ? (
          <div className="px-6 py-12 text-center text-slate-500">
            <p>No sessions found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">
                    Candidate Name
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">
                    Job Title
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left font-semibold text-slate-900">
                    Started Date
                  </th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr
                    key={session.id}
                    className="border-b border-slate-200 hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4 text-slate-900 font-medium">
                      {session.candidateName}
                    </td>
                    <td className="px-6 py-4 text-slate-700">
                      {session.jobTitle}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${
                          statusBadgeMap[session.status]?.color === 'amber'
                            ? 'bg-amber-100 text-amber-900'
                            : statusBadgeMap[session.status]?.color === 'green'
                            ? 'bg-green-100 text-green-900'
                            : statusBadgeMap[session.status]?.color === 'red'
                            ? 'bg-red-100 text-red-900'
                            : 'bg-blue-100 text-blue-900'
                        }`}
                      >
                        {session.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-700">
                      {formatDate(session.startedAt)}
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

'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { getSessions, deleteSession, type SessionItem } from '@/lib/api/sessions';

export default function CandidatesPage() {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  async function handleDelete(sessionId: string) {
    if (!window.confirm('Delete this candidate session? This cannot be undone.')) {
      return;
    }
    setDeletingId(sessionId);
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete session');
    } finally {
      setDeletingId(null);
    }
  }

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getSessions();
        setSessions(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load sessions');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getStatusBadge = (status: string) => {
    const styles = {
      invited: 'bg-blue-100 text-blue-800',
      in_progress: 'bg-amber-100 text-amber-800',
      completed: 'bg-green-100 text-green-800',
      expired: 'bg-red-100 text-red-800',
    };

    return (
      <span className={`px-3 py-1 rounded-full text-xs font-medium ${styles[status as keyof typeof styles] || 'bg-gray-100 text-gray-800'}`}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  const filteredSessions = sessions.filter((s) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (
      s.candidate_name.toLowerCase().includes(q) ||
      s.candidate_email.toLowerCase().includes(q) ||
      s.job_title.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Candidates</h1>

      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search by name, email, or assessment..."
        className="w-full max-w-sm px-4 py-2 border border-slate-300 rounded-lg text-sm focus:outline focus:outline-2 focus:outline-offset-2 focus:outline-slate-900"
      />

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm font-medium text-red-900">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12">
          <p className="text-slate-600">Loading candidates...</p>
        </div>
      ) : sessions.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-12 text-center">
          <p className="text-slate-600">No assessment sessions yet</p>
          <Link
            href="/assessments/create"
            className="mt-4 inline-block px-4 py-2 bg-slate-900 text-white font-medium rounded-lg hover:bg-slate-800"
          >
            Create First Assessment
          </Link>
        </div>
      ) : (
        <div className="overflow-x-auto border border-slate-200 rounded-lg">
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">
                  Candidate Name
                </th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">
                  Candidate Email
                </th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">
                  Assessment
                </th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">
                  Invited
                </th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">
                  Completed
                </th>
                <th className="px-6 py-3 text-right text-sm font-semibold text-slate-900">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredSessions.map((session) => (
                <tr key={session.id} className="border-b border-slate-200 hover:bg-slate-50">
                  <td className="px-6 py-4 text-sm text-slate-900 font-medium">
                    {session.candidate_name}
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-900">
                    {session.candidate_email}
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">
                    {session.job_title}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    {getStatusBadge(session.status)}
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">
                    {formatDate(session.created_at)}
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">
                    {formatDate(session.submitted_at || '')}
                  </td>
                  <td className="px-6 py-4 text-right space-x-3">
                    {session.status === 'completed' && (
                      <Link
                        href={`/candidates/${session.id}/results`}
                        className="text-sm font-medium text-blue-600 hover:text-blue-800"
                      >
                        View Results
                      </Link>
                    )}
                    <button
                      onClick={() => handleDelete(session.id)}
                      disabled={deletingId === session.id}
                      className="text-sm font-medium text-red-600 hover:text-red-800 disabled:opacity-50"
                    >
                      {deletingId === session.id ? 'Deleting…' : 'Delete'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

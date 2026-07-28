'use client';

import { useState } from 'react';
import type { SessionResponse } from '@/lib/types/session';

interface SessionTableProps {
  sessions: SessionResponse[];
  onResendInvite: (sessionId: string) => Promise<void>;
}

const statusColors: Record<string, string> = {
  invited: 'bg-blue-100 text-blue-900',
  in_progress: 'bg-amber-100 text-amber-900',
  completed: 'bg-green-100 text-green-900',
  expired: 'bg-red-100 text-red-900',
};

export default function SessionTable({ sessions, onResendInvite }: SessionTableProps) {
  const [resending, setResending] = useState<string | null>(null);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const handleResend = async (sessionId: string) => {
    setResending(sessionId);
    try {
      await onResendInvite(sessionId);
      alert('Invite resent successfully');
    } finally {
      setResending(null);
    }
  };

  if (sessions.length === 0) {
    return (
      <div className="text-center py-12 bg-slate-50 rounded-lg border border-slate-200">
        <p className="text-slate-600">No sessions yet</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto border border-slate-200 rounded-lg">
      <table className="w-full">
        <thead className="bg-slate-50 border-b border-slate-200">
          <tr>
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
              Created
            </th>
            <th className="px-6 py-3 text-right text-sm font-semibold text-slate-900">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((session) => (
            <tr key={session.id} className="border-b border-slate-200 hover:bg-slate-50">
              <td className="px-6 py-4 text-sm text-slate-900">{session.candidate_email}</td>
              <td className="px-6 py-4 text-sm text-slate-600">{session.job_title}</td>
              <td className="px-6 py-4 text-sm">
                <span
                  className={`inline-block px-2 py-1 rounded-full text-xs font-semibold ${
                    statusColors[session.status] || 'bg-slate-100 text-slate-900'
                  }`}
                >
                  {session.status}
                </span>
              </td>
              <td className="px-6 py-4 text-sm text-slate-600">
                {formatDate(session.created_at)}
              </td>
              <td className="px-6 py-4 text-right">
                {session.status === 'invited' && (
                  <button
                    onClick={() => handleResend(session.id)}
                    disabled={resending === session.id}
                    className="text-sm font-medium text-blue-600 hover:text-blue-800 disabled:opacity-50"
                  >
                    {resending === session.id ? 'Resending...' : 'Resend'}
                  </button>
                )}
                {session.status !== 'invited' && (
                  <span className="text-sm text-slate-600">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

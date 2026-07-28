'use client';

import { useState, useEffect } from 'react';
import { getSessions, resendInvite } from '@/lib/api/sessions';
import SessionTable from '@/components/tables/SessionTable';
import type { SessionResponse } from '@/lib/types/session';

export default function CandidatesPage() {
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const handleResendInvite = async (sessionId: string) => {
    await resendInvite(sessionId);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Candidates & Sessions</h1>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm font-medium text-red-900">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12">
          <p className="text-slate-600">Loading sessions...</p>
        </div>
      ) : (
        <SessionTable sessions={sessions} onResendInvite={handleResendInvite} />
      )}
    </div>
  );
}

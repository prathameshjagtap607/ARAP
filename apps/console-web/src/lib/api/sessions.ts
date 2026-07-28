import { apiFetch } from './index';
import type { SessionResponse } from '@/lib/types/session';

export async function getSessions(): Promise<SessionResponse[]> {
  return apiFetch('/sessions');
}

export async function resendInvite(sessionId: string): Promise<{ link: string; email_sent: boolean }> {
  return apiFetch(`/sessions/${sessionId}/invite`, {
    method: 'POST',
  });
}

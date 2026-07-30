import { apiFetch } from './index';

export interface SessionItem {
  id: string;
  candidate_id: string;
  job_assessment_id: string;
  candidate_email: string;
  job_title: string;
  status: string;
  created_at: string;
  started_at: string | null;
  submitted_at: string | null;
}

export interface SessionReport {
  id: string;
  overall_score: number;
  verdict: string;
  ai_confidence_score: number;
  executive_summary: string;
  strengths: string[];
  risk_flags: string[];
  competency_scores: Record<string, number>;
}

export async function getSessions(): Promise<SessionItem[]> {
  return apiFetch('/sessions');
}

export async function getSessionReport(sessionId: string): Promise<SessionReport> {
  return apiFetch(`/reports/${sessionId}/full`);
}

export interface SendSessionInviteResult {
  link: string;
  email_sent: boolean;
}

export async function sendSessionInvite(
  sessionId: string
): Promise<SendSessionInviteResult> {
  return apiFetch(`/sessions/${sessionId}/invite`, { method: 'POST' });
}

export async function deleteSession(sessionId: string): Promise<void> {
  await apiFetch(`/sessions/${sessionId}`, { method: 'DELETE' });
}

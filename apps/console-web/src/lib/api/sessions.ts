import { apiFetch } from './index';

export interface SessionItem {
  id: string;
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

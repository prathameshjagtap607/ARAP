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

export interface CompositeScore {
  score: number;
  vs_job_bar: string;
  vs_org_bar: string;
}

export interface FullReportBody {
  executive_summary?: string;
  candidate_overview?: string;
  resume_summary?: string;
  interview_summary?: string;
  scores?: Record<string, CompositeScore>;
  overall_rating?: number;
  culture_fit?: string;
  domain_knowledge?: string;
  skill_gap_analysis?: string;
  strengths?: string[];
  weaknesses?: string[];
  potential_risks?: string;
  learning_curve_estimate?: string;
  management_readiness?: string;
  promotion_potential?: string;
  recommended_next_round?: string;
  final_verdict?: string;
  integrity_summary_prose?: string;
}

export interface ReviewerOverride {
  final_decision: 'hire' | 'no_hire' | 'hold';
  comment: string;
  submitted_at: string;
}

export interface SessionReport {
  session_id: string;
  report_ready: boolean;
  requires_human_review: boolean;
  verdict: string | null;
  ai_confidence_score: number | null;
  salary_band: string | null;
  full_report: FullReportBody;
  reviewer_override: ReviewerOverride | null;
  created_at: string | null;
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

export interface ReviewerFeedbackInput {
  final_decision: 'hire' | 'no_hire' | 'hold';
  comment: string;
}

export interface ReviewerFeedbackResult {
  reviewer_override: Record<string, unknown>;
}

export async function submitReviewerFeedback(
  sessionId: string,
  body: ReviewerFeedbackInput
): Promise<ReviewerFeedbackResult> {
  return apiFetch(`/reports/${sessionId}/feedback`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

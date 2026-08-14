import { apiFetch } from './index';

export interface SessionItem {
  id: string;
  candidate_id: string;
  job_assessment_id: string;
  candidate_name: string;
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

export interface DiscProfile {
  primary: string;
  secondary: string;
  confidence: number;
  rationale: string;
}

export interface DevelopmentalInsights {
  natural_leadership_tendencies: string;
  behavioural_strengths: string[];
  potential_blind_spots: string[];
  behaviour_under_pressure: string;
  communication_preferences: string;
  conflict_tendencies: string;
  decision_making_tendencies: string;
  adaptability_assessment: string;
  areas_for_behavioural_development: string[];
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
  disc_profile?: DiscProfile | null;
  developmental_insights?: DevelopmentalInsights | null;
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
  full_report: FullReportBody;
  reviewer_override: ReviewerOverride | null;
  created_at: string | null;
}

export async function getSessions(filterUserId?: string): Promise<SessionItem[]> {
  return apiFetch(`/sessions?${filterUserId ? `filter_user_id=${filterUserId}` : ''}`);
}

export async function getSessionReport(sessionId: string): Promise<SessionReport> {
  return apiFetch(`/reports/${sessionId}/full`);
}

export interface SessionAnswerItem {
  id: string;
  sequence_no: number;
  question: { text: string; options?: Record<string, string>; question_format?: string };
  options: Record<string, string> | null;
  answer_text: string | null;
  adaptive_answer_text: string | null;
  ranking_order: string[] | null;
  reflection_text: string | null;
}

export interface SessionAnswersResponse {
  questions: SessionAnswerItem[];
}

/**
 * Recruiter/admin view of a session's questions with both the candidate's
 * natural and adaptive answers — DISC-Based Generative Leadership Question
 * Framework §8. Uses the /answers endpoint (distinct from the
 * candidate-scoped GET /sessions/{id}).
 */
export async function getSessionAnswers(sessionId: string): Promise<SessionAnswersResponse> {
  return apiFetch(`/sessions/${sessionId}/answers`);
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

export type SessionStatus = 'invited' | 'in_progress' | 'completed' | 'expired';

export interface SessionResponse {
  id: string;
  candidate_email: string;
  job_assessment_id: string;
  job_title: string;
  status: SessionStatus;
  created_at: string;
  started_at: string | null;
  submitted_at: string | null;
  expires_at: string | null;
}

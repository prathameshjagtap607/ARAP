import { apiFetch } from './index';
import type { AssessmentResponse, CreateAssessmentRequest } from '@/lib/types/assessment';

export async function createAssessment(data: CreateAssessmentRequest): Promise<AssessmentResponse> {
  return apiFetch('/job-assessments', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateAssessment(
  id: string,
  data: CreateAssessmentRequest
): Promise<AssessmentResponse> {
  return apiFetch(`/job-assessments/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function getAssessments(filterUserId?: string): Promise<AssessmentResponse[]> {
  return apiFetch(`/job-assessments?${filterUserId ? `filter_user_id=${filterUserId}` : ''}`);
}

export async function getAssessment(id: string): Promise<AssessmentResponse> {
  return apiFetch(`/job-assessments/${id}`);
}

export async function deleteAssessment(id: string): Promise<void> {
  return apiFetch(`/job-assessments/${id}`, {
    method: 'DELETE',
  });
}

export interface SendInviteResult {
  link: string;
  email_sent: boolean;
  session_id: string;
  candidate_id: string;
}

export async function sendInvite(
  assessmentId: string,
  candidateName: string,
  candidateEmail: string,
  timeBudgetSeconds: number
): Promise<SendInviteResult> {
  return apiFetch(`/job-assessments/${assessmentId}/invite`, {
    method: 'POST',
    body: JSON.stringify({
      candidate_name: candidateName,
      candidate_email: candidateEmail,
      time_budget_seconds: timeBudgetSeconds,
    }),
  });
}

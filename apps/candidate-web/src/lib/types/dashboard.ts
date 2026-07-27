export interface CandidateStatusProps {
  jobTitle: string;
  companyName: string;
  sessionState: "invited" | "in_progress" | "completed" | "expired";
  startedAt: string | Date | null;
  completedAt: string | Date | null;
  durationMinutes: number;
  nextSteps: string | null;
}

export interface InterviewDetails {
  format: string;
  duration: number;
  scheduledAt: string | Date;
}

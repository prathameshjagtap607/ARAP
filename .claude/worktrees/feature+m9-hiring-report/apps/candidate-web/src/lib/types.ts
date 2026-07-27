export type AnswerFormat =
  | "multiple_choice"
  | "short_text"
  | "long_text"
  | "video"   // PRD §17 — deferred
  | "voice"   // PRD §17 — deferred
  | "code";   // PRD §17 — deferred

export interface Question {
  id: string;
  sequence_no: number;
  question: { text: string; options?: Record<string, string> };
  category: string;
  target_competencies: string[];
  difficulty: string;
  answer_format: AnswerFormat;
  options: Record<string, string> | null;
  answer_text: string | null;
  answered_at: string | null;
}

export interface SessionData {
  id: string;
  status: "invited" | "in_progress" | "completed" | "expired";
  seconds_remaining: number | null;
  time_budget_seconds: number;
  job_title: string;
  duration_minutes: number;
  questions: Question[];
}

export interface SessionState {
  jwt: string | null;
  session: SessionData | null;
  answers: Record<string, string>;
  currentIndex: number;
  submitting: boolean;
}

export type SessionAction =
  | { type: "SET_JWT"; jwt: string }
  | { type: "SET_SESSION"; session: SessionData }
  | { type: "SET_ANSWER"; questionId: string; text: string }
  | { type: "SET_INDEX"; index: number }
  | { type: "SET_SUBMITTING"; value: boolean }
  | { type: "REHYDRATE"; session: SessionData };

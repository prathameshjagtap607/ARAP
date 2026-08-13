export type AnswerFormat =
  | "multiple_choice"
  | "short_text"
  | "long_text"
  | "video"   // PRD §17 — deferred
  | "voice"   // PRD §17 — deferred
  | "code";   // PRD §17 — deferred

export type QuestionFormat =
  | "situational_response"
  | "first_action"
  | "behavioural_choice"
  | "adaptive_choice"
  | "ranking"
  | "reflection"
  | "self_awareness";

export interface Question {
  id: string;
  sequence_no: number;
  question: { text: string; options?: Record<string, string>; question_format?: QuestionFormat };
  category: string;
  target_competencies: string[];
  difficulty: string;
  answer_format: AnswerFormat;
  options: Record<string, string> | null;
  answer_text: string | null;
  answered_at: string | null;
  // DISC-Based Generative Leadership Question Framework §8 — Natural vs
  // Adaptive Behaviour: the candidate's "most effective, even if not your
  // natural choice" response, captured separately from answer_text above.
  adaptive_answer_text?: string | null;
  adaptive_answered_at?: string | null;
  // §7 Question Formats — 'ranking' and 'reflection' formats capture an
  // additional signal alongside the natural answer_text pick above, which
  // still drives DISC scoring for every question regardless of format.
  ranking_order?: string[] | null;
  ranking_answered_at?: string | null;
  reflection_text?: string | null;
  reflection_answered_at?: string | null;
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
  adaptiveAnswers: Record<string, string>;
  rankingOrders: Record<string, string[]>;
  reflectionTexts: Record<string, string>;
  currentIndex: number;
  submitting: boolean;
}

export type SessionAction =
  | { type: "SET_JWT"; jwt: string }
  | { type: "SET_SESSION"; session: SessionData }
  | { type: "SET_ANSWER"; questionId: string; text: string }
  | { type: "SET_ADAPTIVE_ANSWER"; questionId: string; text: string }
  | { type: "SET_RANKING_ORDER"; questionId: string; order: string[] }
  | { type: "SET_REFLECTION_TEXT"; questionId: string; text: string }
  | { type: "SET_INDEX"; index: number }
  | { type: "SET_SUBMITTING"; value: boolean }
  | { type: "REHYDRATE"; session: SessionData };

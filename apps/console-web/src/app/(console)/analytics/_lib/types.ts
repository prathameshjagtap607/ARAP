export interface ScoreTrendPoint {
  period: string;
  avg_overall: number;
  avg_by_competency: Record<string, number>;
  session_count: number;
}

export interface ScoreTrendsResponse {
  data: ScoreTrendPoint[];
  filters_applied: Record<string, string | null>;
}

export interface FunnelRow {
  department: string;
  role: string;
  total_invited: number;
  completed: number;
  hired: number;
  completion_rate: number;
  hire_rate: number;
}

export interface FunnelResponse {
  rows: FunnelRow[];
  totals: FunnelRow;
}

export interface QuestionCategoryRow {
  category: string;
  difficulty: string;
  question_count: number;
  avg_difficulty_num: number;
  avg_verdict_score: number | null;
}

export interface QuestionAnalyticsResponse {
  rows: QuestionCategoryRow[];
}

export interface BenchmarkResponse {
  session_id: string;
  overall_score: number;
  percentile: number;
  p25: number;
  p50: number;
  p75: number;
  peer_count: number;
}

export interface SkillTrendPoint {
  week_start: string;
  competency: string;
  avg_score: number;
  sample_count: number;
}

export interface SkillTrendsResponse {
  data: SkillTrendPoint[];
  has_data: boolean;
}

export interface AnalyticsFilters {
  dept?: string;
  role?: string;
  from_date?: string;
  to_date?: string;
  granularity?: "week" | "month";
}

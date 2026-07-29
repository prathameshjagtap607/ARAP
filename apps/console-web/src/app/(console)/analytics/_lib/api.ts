import { apiFetch } from "@/lib/api/index";
import type {
  AnalyticsFilters,
  BenchmarkResponse,
  FunnelResponse,
  QuestionAnalyticsResponse,
  ScoreTrendsResponse,
  SkillTrendsResponse,
} from "./types";

function buildQuery(filters: AnalyticsFilters & { job_assessment_id?: string }): string {
  const params = new URLSearchParams();
  if (filters.dept) params.set("dept", filters.dept);
  if (filters.role) params.set("role", filters.role);
  if (filters.from_date) params.set("from_date", filters.from_date);
  if (filters.to_date) params.set("to_date", filters.to_date);
  if (filters.granularity) params.set("granularity", filters.granularity);
  if (filters.job_assessment_id) params.set("job_assessment_id", filters.job_assessment_id);
  const s = params.toString();
  return s ? `?${s}` : "";
}

export async function fetchScoreTrends(
  filters: AnalyticsFilters = {},
  signal?: AbortSignal
): Promise<ScoreTrendsResponse> {
  return apiFetch<ScoreTrendsResponse>(`/analytics/score-trends${buildQuery(filters)}`, { signal });
}

export async function fetchFunnel(
  filters: AnalyticsFilters = {},
  signal?: AbortSignal
): Promise<FunnelResponse> {
  return apiFetch<FunnelResponse>(`/analytics/funnel${buildQuery(filters)}`, { signal });
}

export async function fetchQuestionAnalytics(
  filters: AnalyticsFilters & { job_assessment_id?: string } = {},
  signal?: AbortSignal
): Promise<QuestionAnalyticsResponse> {
  return apiFetch<QuestionAnalyticsResponse>(`/analytics/questions${buildQuery(filters)}`, { signal });
}

export async function fetchBenchmark(
  sessionId: string,
  signal?: AbortSignal
): Promise<BenchmarkResponse> {
  return apiFetch<BenchmarkResponse>(`/analytics/benchmarks/${sessionId}`, { signal });
}

export async function fetchSkillTrends(
  filters: AnalyticsFilters = {},
  signal?: AbortSignal
): Promise<SkillTrendsResponse> {
  return apiFetch<SkillTrendsResponse>(`/analytics/skill-trends${buildQuery(filters)}`, { signal });
}

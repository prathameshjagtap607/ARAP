export const PROMPT_LIBRARY_VERSION = "0.2.0";

export const AGENT_NAMES = [
  "question_generator",
  "report_writer",
  "scorer",
] as const;

export type AgentName = (typeof AGENT_NAMES)[number];

export interface PromptVersion {
  id: string;
  org_id: string | null;
  agent_name: AgentName | string;
  version: string;
  template_body: string;
  is_active: boolean;
  created_at: string;
}

export interface ModelRoutingConfig {
  agent_name: AgentName | string;
  provider: string;
  model_id: string;
  fallback_provider: string | null;
  fallback_model_id: string | null;
  updated_by: string | null;
  updated_at: string;
}

export interface TenantDetail {
  id: string;
  name: string;
  plan_tier: string;
  workspace_limit: number;
  is_active: boolean;
  suspended_at: string | null;
  created_at: string;
  user_count: number;
  session_count: number;
}

export interface HealthOverview {
  queue_depth: number;
  error_rate_24h: number;
  p50_seconds: number | null;
  p95_seconds: number | null;
  p99_seconds: number | null;
  total_sessions_24h: number;
}

export interface IncidentEntry {
  status: string;
  count: number;
  last_seen: string | null;
}

export interface FraudFlagStats {
  total_flags: number;
  false_positive_count: number;
  false_positive_rate: number;
}

import { apiFetch } from "@/lib/api/index";
import type {
  FraudFlagStats,
  HealthOverview,
  IncidentEntry,
  ModelRoutingConfig,
  PromptVersion,
  TenantDetail,
} from "./types";

export async function fetchTenants(signal?: AbortSignal): Promise<TenantDetail[]> {
  return apiFetch<TenantDetail[]>("/admin/tenants", { signal });
}

export async function createTenant(
  payload: { name: string; plan_tier: string; workspace_limit: number },
  signal?: AbortSignal
): Promise<TenantDetail> {
  return apiFetch<TenantDetail>("/admin/tenants", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
}

export async function suspendTenant(orgId: string, signal?: AbortSignal): Promise<TenantDetail> {
  return apiFetch<TenantDetail>(`/admin/tenants/${orgId}/suspend`, {
    method: "DELETE",
    signal,
  });
}

export async function fetchPrompts(signal?: AbortSignal): Promise<PromptVersion[]> {
  return apiFetch<PromptVersion[]>("/admin/prompts", { signal });
}

export async function activatePrompt(id: string, signal?: AbortSignal): Promise<PromptVersion> {
  return apiFetch<PromptVersion>(`/admin/prompts/${id}/activate`, { method: "POST", signal });
}

export async function rollbackPrompt(id: string, signal?: AbortSignal): Promise<PromptVersion> {
  return apiFetch<PromptVersion>(`/admin/prompts/${id}/rollback`, { method: "POST", signal });
}

export async function fetchRoutingConfigs(signal?: AbortSignal): Promise<ModelRoutingConfig[]> {
  return apiFetch<ModelRoutingConfig[]>("/admin/routing", { signal });
}

export async function updateRoutingConfig(
  agentName: string,
  payload: Partial<Pick<ModelRoutingConfig, "provider" | "model_id" | "fallback_provider" | "fallback_model_id">>,
  signal?: AbortSignal
): Promise<ModelRoutingConfig> {
  return apiFetch<ModelRoutingConfig>(`/admin/routing/${agentName}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
}

export async function fetchHealthOverview(signal?: AbortSignal): Promise<HealthOverview> {
  return apiFetch<HealthOverview>("/admin/health/overview", { signal });
}

export async function fetchIncidents(signal?: AbortSignal): Promise<IncidentEntry[]> {
  return apiFetch<IncidentEntry[]>("/admin/health/incidents", { signal });
}

export async function fetchFraudFlags(signal?: AbortSignal): Promise<FraudFlagStats> {
  return apiFetch<FraudFlagStats>("/admin/health/fraud-flags", { signal });
}

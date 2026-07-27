import { apiFetch } from "./index";
import type {
  DashboardSession,
  HRDashboardData,
  ReportRow,
  ReportsDashboardData,
  AdminDashboardData,
} from "@/lib/types/dashboard";

/**
 * Transform snake_case API response fields to camelCase
 */
function toCamelCase(obj: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const camelKey = key.replace(/_([a-z])/g, (_, char) => char.toUpperCase());
    result[camelKey] = value;
  }
  return result;
}

/**
 * Fetch HR Dashboard counts: active assessments, in-progress candidates, awaiting review, pending decisions
 */
export async function fetchHRDashboardCounts(
  orgId: string,
  abortSignal?: AbortSignal
): Promise<Omit<HRDashboardData, "recentSessions" | "completionTrend">> {
  try {
    const [activeAssessments, inProgressSessions, awaitingReviewReports] =
      await Promise.all([
        apiFetch<{ count: number }>(
          `/assessments?org_id=${orgId}&active=true`,
          { signal: abortSignal }
        ).then((r) => r.count),
        apiFetch<{ items: { candidate_id: string }[] }>(
          `/sessions?org_id=${orgId}&status=in_progress&limit=1000`,
          { signal: abortSignal }
        ).then((r) => new Set(r.items?.map((s) => s.candidate_id) || []).size),
        apiFetch<{ count: number }>(
          `/reports?org_id=${orgId}&status=awaiting_review`,
          { signal: abortSignal }
        ).then((r) => r.count),
      ]);

    return {
      activeAssessments: activeAssessments || 0,
      candidatesInProgress: inProgressSessions || 0,
      awaitingReview: awaitingReviewReports || 0,
      pendingDecisions: 0, // Computed from reports if needed
    };
  } catch (error) {
    console.error("[fetchHRDashboardCounts] Error:", error);
    return {
      activeAssessments: 0,
      candidatesInProgress: 0,
      awaitingReview: 0,
      pendingDecisions: 0,
    };
  }
}

/**
 * Fetch recent sessions with optional status filter and limit
 */
export async function fetchRecentSessions(
  orgId: string,
  status?: string,
  limit: number = 10,
  abortSignal?: AbortSignal
): Promise<DashboardSession[]> {
  try {
    const statusParam = status ? `&status=${status}` : "";
    const response = await apiFetch<{ items: Record<string, unknown>[] }>(
      `/sessions?org_id=${orgId}${statusParam}&limit=${limit}`,
      { signal: abortSignal }
    );

    return (response.items || []).map((session) => {
      const camelSession = toCamelCase(session);
      return {
        id: String(camelSession.id),
        candidateName: String(camelSession.candidateName || ""),
        jobTitle: String(camelSession.jobTitle || ""),
        status: (camelSession.status as DashboardSession["status"]) || "invited",
        startedAt: camelSession.startedAt ? String(camelSession.startedAt) : null,
        createdAt: String(camelSession.createdAt || ""),
      };
    });
  } catch (error) {
    console.error("[fetchRecentSessions] Error:", error);
    return [];
  }
}

/**
 * Fetch reports list with filters, pagination support
 */
export async function fetchReportsList(
  orgId: string,
  filters?: Record<string, unknown>,
  limit: number = 20,
  offset: number = 0,
  abortSignal?: AbortSignal
): Promise<ReportsDashboardData> {
  try {
    const queryParams = new URLSearchParams({
      org_id: orgId,
      limit: String(limit),
      offset: String(offset),
    });

    if (filters) {
      if (filters.verdict) {
        queryParams.append("verdict", String(filters.verdict));
      }
      if (filters.dateFrom) {
        queryParams.append("date_from", String(filters.dateFrom));
      }
      if (filters.dateTo) {
        queryParams.append("date_to", String(filters.dateTo));
      }
    }

    const response = await apiFetch<{
      items: Record<string, unknown>[];
      total_count: number;
    }>(`/reports?${queryParams}`, { signal: abortSignal });

    const reports: ReportRow[] = (response.items || []).map((report) => {
      const camelReport = toCamelCase(report);
      return {
        id: String(camelReport.id),
        candidateName: String(camelReport.candidateName || ""),
        jobTitle: String(camelReport.jobTitle || ""),
        verdict: (camelReport.verdict as ReportRow["verdict"]) || "consider",
        overallScore: Number(camelReport.overallScore || 0),
        createdAt: String(camelReport.createdAt || ""),
      };
    });

    // Compute verdict and score band distributions
    const verdictDistribution: { verdict: string; count: number }[] = [];
    const verdictCounts = new Map<string, number>();

    reports.forEach((r) => {
      verdictCounts.set(r.verdict, (verdictCounts.get(r.verdict) || 0) + 1);
    });

    verdictCounts.forEach((count, verdict) => {
      verdictDistribution.push({ verdict, count });
    });

    const scoreBandDistribution: { band: string; count: number }[] = [
      { band: "4.5-5.0", count: 0 },
      { band: "4.0-4.4", count: 0 },
      { band: "3.5-3.9", count: 0 },
      { band: "3.0-3.4", count: 0 },
      { band: "<3.0", count: 0 },
    ];

    reports.forEach((r) => {
      if (r.overallScore >= 4.5) scoreBandDistribution[0].count++;
      else if (r.overallScore >= 4.0) scoreBandDistribution[1].count++;
      else if (r.overallScore >= 3.5) scoreBandDistribution[2].count++;
      else if (r.overallScore >= 3.0) scoreBandDistribution[3].count++;
      else scoreBandDistribution[4].count++;
    });

    return {
      reports,
      verdictDistribution,
      scoreBandDistribution,
      totalCount: response.total_count || 0,
      currentPage: Math.floor(offset / limit),
      pageSize: limit,
    };
  } catch (error) {
    console.error("[fetchReportsList] Error:", error);
    return {
      reports: [],
      verdictDistribution: [],
      scoreBandDistribution: [],
      totalCount: 0,
      currentPage: 0,
      pageSize: limit,
    };
  }
}

/**
 * Fetch admin dashboard data: users, competencies, templates
 */
export async function fetchAdminDashboard(
  orgId: string,
  abortSignal?: AbortSignal
): Promise<AdminDashboardData> {
  try {
    const [usersResponse, competenciesResponse, templatesResponse] =
      await Promise.all([
        apiFetch<{ items: Record<string, unknown>[]; total_count: number }>(
          `/users?org_id=${orgId}`,
          { signal: abortSignal }
        ),
        apiFetch<{ items: Record<string, unknown>[]; total_count: number }>(
          `/competency-library?org_id=${orgId}`,
          { signal: abortSignal }
        ),
        apiFetch<{ items: Record<string, unknown>[]; total_count: number }>(
          `/role-templates?org_id=${orgId}`,
          { signal: abortSignal }
        ),
      ]);

    const users = (usersResponse.items || []).map((user) => {
      const camelUser = toCamelCase(user);
      return {
        id: String(camelUser.id),
        name: String(camelUser.name || ""),
        email: String(camelUser.email || ""),
        role: (camelUser.role as "admin" | "user") || "user",
        createdAt: String(camelUser.createdAt || ""),
      };
    });

    const competencies = (competenciesResponse.items || []).map((comp) => {
      const camelComp = toCamelCase(comp);
      return {
        id: String(camelComp.id),
        name: String(camelComp.name || ""),
        category: String(camelComp.category || ""),
        createdAt: String(camelComp.createdAt || ""),
        entryCount: Number(camelComp.entryCount || 0),
      };
    });

    const templates = (templatesResponse.items || []).map((tpl) => {
      const camelTpl = toCamelCase(tpl);
      return {
        id: String(camelTpl.id),
        name: String(camelTpl.name || ""),
        competencyCount: Number(camelTpl.competencyCount || 0),
        createdAt: String(camelTpl.createdAt || ""),
      };
    });

    return {
      totalUsers: usersResponse.total_count || users.length,
      competencyCount: competenciesResponse.total_count || competencies.length,
      templateCount: templatesResponse.total_count || templates.length,
      users,
      competencies,
      templates,
    };
  } catch (error) {
    console.error("[fetchAdminDashboard] Error:", error);
    return {
      totalUsers: 0,
      competencyCount: 0,
      templateCount: 0,
      users: [],
      competencies: [],
      templates: [],
    };
  }
}

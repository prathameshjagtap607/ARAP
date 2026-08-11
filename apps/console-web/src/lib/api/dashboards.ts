import { apiFetch, getAuthToken } from "./index";
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
    const [assessments, sessions, awaitingReviewReports] = await Promise.all([
      apiFetch<{ is_template: boolean }[]>(`/job-assessments`, { signal: abortSignal }),
      apiFetch<{ candidate_email: string; status: string }[]>(`/sessions`, {
        signal: abortSignal,
      }),
      apiFetch<{ total_count: number }>(
        `/reports?status=awaiting_review`,
        { signal: abortSignal }
      ),
    ]);

    const activeAssessments = (assessments || []).filter((a) => !a.is_template).length;
    const inProgressCandidates = new Set(
      (sessions || [])
        .filter((s) => s.status === "in_progress")
        .map((s) => s.candidate_email)
    ).size;

    return {
      activeAssessments,
      candidatesInProgress: inProgressCandidates,
      awaitingReview: awaitingReviewReports.total_count || 0,
      // Reports with a verdict but no reviewer_override yet — same condition
      // the backend already uses for "awaiting_review" (see reports/service.py).
      pendingDecisions: awaitingReviewReports.total_count || 0,
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
    const sessions = await apiFetch<Record<string, unknown>[]>(`/sessions`, {
      signal: abortSignal,
    });

    const filtered = (sessions || []).filter(
      (session) => !status || session.status === status
    );

    return filtered.slice(0, limit).map((session) => {
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
      limit: String(limit),
      offset: String(offset),
    });

    if (filters) {
      if (filters.discCategory) {
        queryParams.append("disc_category", String(filters.discCategory));
      }
      if (Array.isArray(filters.discConfidence)) {
        filters.discConfidence.forEach((band) =>
          queryParams.append("disc_confidence_band", String(band))
        );
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
        sessionId: String(camelReport.sessionId),
        candidateName: String(camelReport.candidateName || ""),
        jobTitle: String(camelReport.jobTitle || ""),
        discPrimary: (camelReport.discPrimary as ReportRow["discPrimary"]) ?? null,
        discConfidence:
          camelReport.discConfidence != null ? Number(camelReport.discConfidence) : null,
        createdAt: String(camelReport.createdAt || ""),
      };
    });

    // Compute DISC category and confidence distributions
    const discCategoryDistribution: { category: string; count: number }[] = [];
    const categoryCounts = new Map<string, number>();

    reports.forEach((r) => {
      const category = r.discPrimary || "Unclassified";
      categoryCounts.set(category, (categoryCounts.get(category) || 0) + 1);
    });

    categoryCounts.forEach((count, category) => {
      discCategoryDistribution.push({ category, count });
    });

    const discConfidenceDistribution: { band: string; count: number }[] = [
      { band: "80-100%", count: 0 },
      { band: "60-79%", count: 0 },
      { band: "40-59%", count: 0 },
      { band: "<40%", count: 0 },
    ];

    reports.forEach((r) => {
      if (r.discConfidence == null) return;
      const pct = r.discConfidence * 100;
      if (pct >= 80) discConfidenceDistribution[0].count++;
      else if (pct >= 60) discConfidenceDistribution[1].count++;
      else if (pct >= 40) discConfidenceDistribution[2].count++;
      else discConfidenceDistribution[3].count++;
    });

    return {
      reports,
      discCategoryDistribution,
      discConfidenceDistribution,
      totalCount: response.total_count || 0,
      currentPage: Math.floor(offset / limit),
      pageSize: limit,
    };
  } catch (error) {
    console.error("[fetchReportsList] Error:", error);
    return {
      reports: [],
      discCategoryDistribution: [],
      discConfidenceDistribution: [],
      totalCount: 0,
      currentPage: 0,
      pageSize: limit,
    };
  }
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Create a new workspace user (Admin only).
 */
export async function createUser(input: {
  email: string;
  role: "user" | "admin";
  password: string;
}): Promise<{ id: string; email: string; role: string; createdAt: string }> {
  const response = await apiFetch<Record<string, unknown>>(`/users`, {
    method: "POST",
    body: JSON.stringify(input),
  });
  const camel = toCamelCase(response);
  return {
    id: String(camel.id),
    email: String(camel.email),
    role: String(camel.role),
    createdAt: String(camel.createdAt),
  };
}

/**
 * Download a candidate's hiring report as a PDF and trigger a browser save.
 */
export async function downloadReportPdf(sessionId: string): Promise<void> {
  const token = getAuthToken();
  const res = await fetch(`${BASE_URL}/reports/${sessionId}/pdf`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!res.ok) {
    throw new Error(`Failed to download report (HTTP ${res.status})`);
  }

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `report-${sessionId}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

/**
 * Fetch admin dashboard data: users, competencies, templates
 */
export async function fetchAdminDashboard(
  orgId: string,
  abortSignal?: AbortSignal
): Promise<AdminDashboardData> {
  try {
    const [usersResponse, competenciesResponse, jobAssessments] = await Promise.all([
      apiFetch<{ items: Record<string, unknown>[]; total_count: number }>(`/users`, {
        signal: abortSignal,
      }),
      apiFetch<Record<string, unknown>[]>(`/competency-library`, { signal: abortSignal }),
      apiFetch<Record<string, unknown>[]>(`/job-assessments`, { signal: abortSignal }),
    ]);

    const users = (usersResponse.items || []).map((user) => {
      const camelUser = toCamelCase(user);
      return {
        id: String(camelUser.id),
        name: String(camelUser.email || ""),
        email: String(camelUser.email || ""),
        role: (camelUser.role as "admin" | "user") || "user",
        createdAt: String(camelUser.createdAt || ""),
      };
    });

    const competencies = (competenciesResponse || []).map((comp) => {
      const camelComp = toCamelCase(comp);
      return {
        id: String(camelComp.id),
        name: String(camelComp.name || ""),
        category: "General",
        createdAt: String(camelComp.createdAt || ""),
        entryCount: 1,
      };
    });

    const templateRows = (jobAssessments || []).filter(
      (job) => job.is_template === true
    );
    const templates = templateRows.map((tpl) => {
      const camelTpl = toCamelCase(tpl);
      const weightage = (camelTpl.competencyWeightage as Record<string, unknown>) || {};
      return {
        id: String(camelTpl.id),
        name: String(camelTpl.title || ""),
        competencyCount: Object.keys(weightage).length,
        createdAt: String(camelTpl.createdAt || ""),
      };
    });

    return {
      totalUsers: usersResponse.total_count || users.length,
      competencyCount: competencies.length,
      templateCount: templates.length,
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

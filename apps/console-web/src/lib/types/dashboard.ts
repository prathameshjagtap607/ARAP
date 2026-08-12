import React from "react";

// Filter configuration for FilterBar component
export interface Filter {
  key: string;
  label: string;
  type: "date-range" | "select" | "search" | "multi-select";
  options?: { label: string; value: string }[];
  placeholder?: string;
}

// SummaryCard props
export interface SummaryCardProps {
  title: string;
  value: string | number;
  badge?: { label: string; color: "amber" | "green" | "red" | "blue" };
  icon?: React.ReactNode;
  trend?: { value: number; direction: "up" | "down" | "flat" };
  onClick?: () => void;
  loading?: boolean;
}

// ChartCard props
export interface ChartCardProps {
  title: string;
  data: unknown[];
  chartType: "bar" | "line" | "pie" | "composed";
  xKey?: string;
  yKey?: string;
  series?: { key: string; fill: string }[];
  height?: number;
  loading?: boolean;
}

// HR Dashboard session row
export interface DashboardSession {
  id: string;
  candidateName: string;
  jobTitle: string;
  status: "invited" | "in_progress" | "completed" | "expired";
  startedAt: string | null;
  createdAt: string;
}

// HR Dashboard summary
export interface HRDashboardData {
  activeAssessments: number;
  candidatesInProgress: number;
  awaitingReview: number;
  candidatesInvited: number;
  candidatesCompleted: number;
  recentSessions: DashboardSession[];
  completionTrend?: { date: string; count: number }[];
}

// Reports Dashboard filter result
export interface ReportRow {
  id: string;
  sessionId: string;
  candidateName: string;
  jobTitle: string;
  discPrimary: "D" | "I" | "S" | "C" | null;
  discConfidence: number | null;
  createdAt: string;
}

// Reports Dashboard summary
export interface ReportsDashboardData {
  reports: ReportRow[];
  discCategoryDistribution: { category: string; count: number }[];
  discConfidenceDistribution: { band: string; count: number }[];
  totalCount: number;
  currentPage: number;
  pageSize: number;
}

// Admin Dashboard summary
export interface AdminDashboardData {
  totalUsers: number;
  competencyCount: number;
  templateCount: number;
  users: {
    id: string;
    name: string;
    email: string;
    role: "admin" | "user";
    createdAt: string;
  }[];
  competencies: {
    id: string;
    name: string;
    category: string;
    createdAt: string;
    entryCount: number;
  }[];
  templates: {
    id: string;
    name: string;
    competencyCount: number;
    createdAt: string;
  }[];
}

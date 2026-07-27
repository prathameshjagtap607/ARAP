# M10 Dashboards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build four role-scoped dashboards (HR, Admin, Reports, Candidate) using a shared component library (SummaryCard, FilterBar, ChartCard) to surface hiring pipeline state, org admin, and candidate progress.

**Architecture:** Frontend-only composition layer over existing M1–M9 API endpoints. No new backend routes. Reusable component library prevents duplication across four dashboard implementations. Candidate view enforces score-safety via TypeScript schema separation and role-gated API contracts.

**Tech Stack:** Next.js 14 App Router, TypeScript 5.x (strict mode), Recharts 2.x, React Query (if available; else fetch), Tailwind CSS.

## Global Constraints

- **Scope:** console-web `src/app/(console)/dashboard/` + candidate-web `src/app/status/` only
- **No new backend endpoints:** Use existing M1–M9 API surfaces
- **Candidate score safety:** TypeScript schema strict separation; `require_user` gates score-bearing endpoints
- **Component reuse:** SummaryCard, FilterBar, ChartCard must be implemented once per app (duplication acceptable at MVP scale)
- **Type safety:** TypeScript strict mode enabled; all props fully typed
- **Styling:** Match existing Tailwind CSS palette from TASK-001 console shell
- **Accessibility:** WCAG 2.1 AA focus rings on all interactive elements (copy from candidate-web pattern)
- **Testing:** Unit tests for components, integration tests for page-level data flows

---

## Task 1: Setup Types & API Helpers (console-web)

**Files:**
- Create: `apps/console-web/src/lib/types/dashboard.ts`
- Create: `apps/console-web/src/lib/api/dashboards.ts`

**Interfaces:**
- Produces: `Filter`, `SummaryCardProps`, `ChartCardProps`, `DashboardSession`, and API helper functions (`fetchAssessmentCounts()`, `fetchSessionTrend()`, `fetchReportsList()`, etc.)

**Steps:**

- [ ] **Step 1: Create dashboard types file**

Create `apps/console-web/src/lib/types/dashboard.ts`:

```typescript
// Filter configuration for FilterBar component
export interface Filter {
  key: string;
  label: string;
  type: 'date-range' | 'select' | 'search' | 'multi-select';
  options?: { label: string; value: string }[];
  placeholder?: string;
}

// SummaryCard props
export interface SummaryCardProps {
  title: string;
  value: string | number;
  badge?: { label: string; color: 'amber' | 'green' | 'red' | 'blue' };
  icon?: React.ReactNode;
  trend?: { value: number; direction: 'up' | 'down' | 'flat' };
  onClick?: () => void;
  loading?: boolean;
}

// ChartCard props
export interface ChartCardProps {
  title: string;
  data: unknown[];
  chartType: 'bar' | 'line' | 'pie' | 'composed';
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
  status: 'invited' | 'in_progress' | 'completed' | 'expired';
  startedAt: string | null;
  createdAt: string;
}

// HR Dashboard summary
export interface HRDashboardData {
  activeAssessments: number;
  candidatesInProgress: number;
  awaitingReview: number;
  pendingDecisions: number;
  recentSessions: DashboardSession[];
  completionTrend?: { date: string; count: number }[];
}

// Reports Dashboard filter result
export interface ReportRow {
  id: string;
  candidateName: string;
  jobTitle: string;
  verdict: 'strong_hire' | 'hire' | 'consider' | 'borderline' | 'reject';
  overallScore: number;
  createdAt: string;
}

// Reports Dashboard summary
export interface ReportsDashboardData {
  reports: ReportRow[];
  verdictDistribution: { verdict: string; count: number }[];
  scoreBandDistribution: { band: string; count: number }[];
  totalCount: number;
  currentPage: number;
  pageSize: number;
}

// Admin Dashboard summary
export interface AdminDashboardData {
  totalUsers: number;
  competencyCount: number;
  templateCount: number;
  users: { id: string; name: string; email: string; role: 'admin' | 'user'; createdAt: string }[];
  competencies: { id: string; name: string; category: string; createdAt: string; entryCount: number }[];
  templates: { id: string; name: string; competencyCount: number; createdAt: string }[];
}
```

- [ ] **Step 2: Create API helpers file**

Create `apps/console-web/src/lib/api/dashboards.ts`:

```typescript
import { apiFetch } from './index'; // Use existing API client from TASK-001
import type {
  HRDashboardData,
  ReportsDashboardData,
  ReportRow,
  AdminDashboardData,
} from '@/lib/types/dashboard';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Fetch HR Dashboard summary counts
 */
export async function fetchHRDashboardCounts(
  orgId: string,
  abortSignal?: AbortSignal
): Promise<Omit<HRDashboardData, 'recentSessions' | 'completionTrend'>> {
  try {
    const [active, inProgress, awaiting, pending] = await Promise.all([
      apiFetch<{ total: number }>(
        `${API_BASE}/assessments?org_id=${orgId}&active=true`,
        { signal: abortSignal }
      ),
      apiFetch<{ total: number }>(
        `${API_BASE}/sessions?org_id=${orgId}&status=in_progress`,
        { signal: abortSignal }
      ),
      apiFetch<{ total: number }>(
        `${API_BASE}/reports?org_id=${orgId}&status=awaiting_review`,
        { signal: abortSignal }
      ),
      apiFetch<{ total: number }>(
        `${API_BASE}/reports?org_id=${orgId}&status=pending_decision`,
        { signal: abortSignal }
      ),
    ]);

    return {
      activeAssessments: active?.total || 0,
      candidatesInProgress: inProgress?.total || 0,
      awaitingReview: awaiting?.total || 0,
      pendingDecisions: pending?.total || 0,
    };
  } catch (error) {
    console.error('Failed to fetch HR dashboard counts:', error);
    return {
      activeAssessments: 0,
      candidatesInProgress: 0,
      awaitingReview: 0,
      pendingDecisions: 0,
    };
  }
}

/**
 * Fetch recent sessions for HR Dashboard
 */
export async function fetchRecentSessions(
  orgId: string,
  status?: string,
  limit: number = 10,
  abortSignal?: AbortSignal
): Promise<DashboardSession[]> {
  try {
    const url = new URL(`${API_BASE}/sessions`);
    url.searchParams.append('org_id', orgId);
    url.searchParams.append('limit', limit.toString());
    if (status) url.searchParams.append('status', status);

    const response = await apiFetch<{
      data: Array<{
        id: string;
        candidate_name: string;
        job_title: string;
        status: string;
        started_at: string | null;
        created_at: string;
      }>;
    }>(url.toString(), { signal: abortSignal });

    return (
      response?.data?.map((s) => ({
        id: s.id,
        candidateName: s.candidate_name,
        jobTitle: s.job_title,
        status: s.status as DashboardSession['status'],
        startedAt: s.started_at,
        createdAt: s.created_at,
      })) || []
    );
  } catch (error) {
    console.error('Failed to fetch recent sessions:', error);
    return [];
  }
}

/**
 * Fetch Reports Dashboard list with filters and pagination
 */
export async function fetchReportsList(
  orgId: string,
  filters: {
    verdicts?: string[];
    scoreBands?: string[];
    startDate?: string;
    endDate?: string;
    search?: string;
  },
  limit: number = 20,
  offset: number = 0,
  abortSignal?: AbortSignal
): Promise<ReportsDashboardData> {
  try {
    const url = new URL(`${API_BASE}/reports`);
    url.searchParams.append('org_id', orgId);
    url.searchParams.append('status', 'completed');
    url.searchParams.append('limit', limit.toString());
    url.searchParams.append('offset', offset.toString());

    if (filters.verdicts?.length) {
      url.searchParams.append('verdicts', filters.verdicts.join(','));
    }
    if (filters.startDate) url.searchParams.append('start_date', filters.startDate);
    if (filters.endDate) url.searchParams.append('end_date', filters.endDate);
    if (filters.search) url.searchParams.append('search', filters.search);

    const response = await apiFetch<{
      data: Array<{
        id: string;
        candidate_name: string;
        job_title: string;
        verdict: string;
        overall_score: number;
        created_at: string;
      }>;
      total: number;
      verdict_distribution: { verdict: string; count: number }[];
      score_band_distribution: { band: string; count: number }[];
    }>(url.toString(), { signal: abortSignal });

    return {
      reports:
        response?.data?.map((r) => ({
          id: r.id,
          candidateName: r.candidate_name,
          jobTitle: r.job_title,
          verdict: r.verdict as ReportRow['verdict'],
          overallScore: r.overall_score,
          createdAt: r.created_at,
        })) || [],
      verdictDistribution: response?.verdict_distribution || [],
      scoreBandDistribution: response?.score_band_distribution || [],
      totalCount: response?.total || 0,
      currentPage: Math.floor(offset / limit),
      pageSize: limit,
    };
  } catch (error) {
    console.error('Failed to fetch reports list:', error);
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
 * Fetch Admin Dashboard data
 */
export async function fetchAdminDashboard(
  orgId: string,
  abortSignal?: AbortSignal
): Promise<AdminDashboardData> {
  try {
    const [users, competencies, templates] = await Promise.all([
      apiFetch<{
        data: Array<{
          id: string;
          name: string;
          email: string;
          role: string;
          created_at: string;
        }>;
      }>(`${API_BASE}/users?org_id=${orgId}`, { signal: abortSignal }),
      apiFetch<{
        data: Array<{
          id: string;
          name: string;
          category: string;
          created_at: string;
          entry_count: number;
        }>;
      }>(`${API_BASE}/competency-library?org_id=${orgId}`, { signal: abortSignal }),
      apiFetch<{
        data: Array<{
          id: string;
          name: string;
          competency_count: number;
          created_at: string;
        }>;
      }>(`${API_BASE}/role-templates?org_id=${orgId}`, { signal: abortSignal }),
    ]);

    return {
      totalUsers: users?.data?.length || 0,
      competencyCount: competencies?.data?.length || 0,
      templateCount: templates?.data?.length || 0,
      users:
        users?.data?.map((u) => ({
          id: u.id,
          name: u.name,
          email: u.email,
          role: u.role as 'admin' | 'user',
          createdAt: u.created_at,
        })) || [],
      competencies:
        competencies?.data?.map((c) => ({
          id: c.id,
          name: c.name,
          category: c.category,
          createdAt: c.created_at,
          entryCount: c.entry_count,
        })) || [],
      templates:
        templates?.data?.map((t) => ({
          id: t.id,
          name: t.name,
          competencyCount: t.competency_count,
          createdAt: t.created_at,
        })) || [],
    };
  } catch (error) {
    console.error('Failed to fetch admin dashboard:', error);
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
```

- [ ] **Step 3: Commit types and API helpers**

```bash
git add apps/console-web/src/lib/types/dashboard.ts apps/console-web/src/lib/api/dashboards.ts
git commit -m "feat(dashboard): add types and API helpers for M10 dashboards"
```

---

## Task 2: Build SummaryCard Component (console-web)

**Files:**
- Create: `apps/console-web/src/components/dashboard/SummaryCard.tsx`
- Create: `apps/console-web/src/components/dashboard/__tests__/SummaryCard.test.tsx`

**Interfaces:**
- Consumes: `SummaryCardProps` from Task 1
- Produces: `SummaryCard` React component exported as default

**Steps:**

- [ ] **Step 1: Write test for SummaryCard**

Create `apps/console-web/src/components/dashboard/__tests__/SummaryCard.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react';
import SummaryCard from '../SummaryCard';
import type { SummaryCardProps } from '@/lib/types/dashboard';

describe('SummaryCard', () => {
  it('renders title and value', () => {
    const props: SummaryCardProps = {
      title: 'Active Assessments',
      value: 12,
    };
    render(<SummaryCard {...props} />);
    expect(screen.getByText('Active Assessments')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
  });

  it('renders badge when provided', () => {
    const props: SummaryCardProps = {
      title: 'Status',
      value: 5,
      badge: { label: 'Active', color: 'green' },
    };
    render(<SummaryCard {...props} />);
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('renders loading skeleton when loading is true', () => {
    const props: SummaryCardProps = {
      title: 'Loading',
      value: 0,
      loading: true,
    };
    const { container } = render(<SummaryCard {...props} />);
    expect(container.querySelector('[data-testid="loading-skeleton"]')).toBeInTheDocument();
  });

  it('renders trend indicator when provided', () => {
    const props: SummaryCardProps = {
      title: 'Trend',
      value: 10,
      trend: { value: 2, direction: 'up' },
    };
    render(<SummaryCard {...props} />);
    expect(screen.getByText('+2')).toBeInTheDocument();
  });

  it('calls onClick handler when clicked', () => {
    const onClick = jest.fn();
    const props: SummaryCardProps = {
      title: 'Clickable',
      value: 1,
      onClick,
    };
    const { container } = render(<SummaryCard {...props} />);
    container.querySelector('button')?.click();
    expect(onClick).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd apps/console-web
npm test -- src/components/dashboard/__tests__/SummaryCard.test.tsx
```

Expected: FAIL with "SummaryCard not found" or similar.

- [ ] **Step 3: Implement SummaryCard component**

Create `apps/console-web/src/components/dashboard/SummaryCard.tsx`:

```typescript
import type { SummaryCardProps } from '@/lib/types/dashboard';

const badgeColorMap = {
  amber: 'bg-amber-100 text-amber-900',
  green: 'bg-green-100 text-green-900',
  red: 'bg-red-100 text-red-900',
  blue: 'bg-blue-100 text-blue-900',
};

const trendDirectionMap = {
  up: '↑',
  down: '↓',
  flat: '→',
};

export default function SummaryCard({
  title,
  value,
  badge,
  icon,
  trend,
  onClick,
  loading,
}: SummaryCardProps) {
  if (loading) {
    return (
      <div
        data-testid="loading-skeleton"
        className="rounded-lg border border-slate-200 bg-white p-6 animate-pulse"
      >
        <div className="h-4 w-24 bg-slate-200 rounded mb-4" />
        <div className="h-8 w-16 bg-slate-200 rounded" />
      </div>
    );
  }

  const Wrapper = onClick ? 'button' : 'div';
  const wrapperProps = onClick ? { onClick, type: 'button' as const } : {};

  return (
    <Wrapper
      {...wrapperProps}
      className={`rounded-lg border border-slate-200 bg-white p-6 ${
        onClick ? 'hover:border-slate-300 cursor-pointer transition-colors' : ''
      }`}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-600">{title}</p>
          <div className="mt-2 flex items-baseline gap-2">
            {icon && <span className="text-xl">{icon}</span>}
            <p className="text-3xl font-bold text-slate-900">{value}</p>
          </div>
        </div>
        {badge && (
          <span className={`inline-block px-2 py-1 rounded text-xs font-semibold ${badgeColorMap[badge.color]}`}>
            {badge.label}
          </span>
        )}
      </div>
      {trend && (
        <div className="mt-4 text-sm">
          <span className={trend.direction === 'up' ? 'text-green-600' : trend.direction === 'down' ? 'text-red-600' : 'text-slate-600'}>
            {trendDirectionMap[trend.direction]} {trend.value > 0 ? '+' : ''}{trend.value}
          </span>
        </div>
      )}
    </Wrapper>
  );
}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd apps/console-web
npm test -- src/components/dashboard/__tests__/SummaryCard.test.tsx
```

Expected: PASS (all 5 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/console-web/src/components/dashboard/
git commit -m "feat(dashboard): add SummaryCard component with tests"
```

---

## Task 3: Build FilterBar Component (console-web)

**Files:**
- Create: `apps/console-web/src/components/dashboard/FilterBar.tsx`
- Create: `apps/console-web/src/components/dashboard/__tests__/FilterBar.test.tsx`

**Interfaces:**
- Consumes: `Filter` from Task 1
- Produces: `FilterBar` component exported as default

**Steps:**

- [ ] **Step 1: Write test for FilterBar**

Create `apps/console-web/src/components/dashboard/__tests__/FilterBar.test.tsx`:

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import FilterBar from '../FilterBar';
import type { Filter } from '@/lib/types/dashboard';

describe('FilterBar', () => {
  const mockOnApply = jest.fn();
  const mockOnReset = jest.fn();

  const filters: Filter[] = [
    {
      key: 'status',
      label: 'Status',
      type: 'select',
      options: [
        { label: 'Active', value: 'active' },
        { label: 'Inactive', value: 'inactive' },
      ],
    },
    {
      key: 'date_range',
      label: 'Date Range',
      type: 'date-range',
    },
  ];

  it('renders filter labels', () => {
    render(
      <FilterBar filters={filters} onApply={mockOnApply} onReset={mockOnReset} />
    );
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Date Range')).toBeInTheDocument();
  });

  it('calls onApply when Apply button is clicked', () => {
    render(
      <FilterBar filters={filters} onApply={mockOnApply} onReset={mockOnReset} />
    );
    fireEvent.click(screen.getByText('Apply'));
    expect(mockOnApply).toHaveBeenCalled();
  });

  it('calls onReset when Reset button is clicked', () => {
    render(
      <FilterBar filters={filters} onApply={mockOnApply} onReset={mockOnReset} />
    );
    fireEvent.click(screen.getByText('Reset'));
    expect(mockOnReset).toHaveBeenCalled();
  });

  it('renders loading state', () => {
    const { container } = render(
      <FilterBar
        filters={filters}
        onApply={mockOnApply}
        onReset={mockOnReset}
        loading={true}
      />
    );
    const buttons = container.querySelectorAll('button');
    buttons.forEach((btn) => {
      expect(btn).toBeDisabled();
    });
  });
});
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd apps/console-web
npm test -- src/components/dashboard/__tests__/FilterBar.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement FilterBar component**

Create `apps/console-web/src/components/dashboard/FilterBar.tsx`:

```typescript
'use client';

import { useState } from 'react';
import type { Filter } from '@/lib/types/dashboard';

interface FilterBarProps {
  filters: Filter[];
  onApply: (values: Record<string, any>) => void;
  onReset: () => void;
  loading?: boolean;
}

export default function FilterBar({
  filters,
  onApply,
  onReset,
  loading = false,
}: FilterBarProps) {
  const [values, setValues] = useState<Record<string, any>>({});

  const handleChange = (key: string, value: any) => {
    setValues((prev) => ({ ...prev, [key]: value }));
  };

  const handleApply = () => {
    onApply(values);
  };

  const handleReset = () => {
    setValues({});
    onReset();
  };

  return (
    <div className="flex flex-wrap gap-4 p-4 bg-slate-50 rounded-lg border border-slate-200">
      {filters.map((filter) => (
        <div key={filter.key} className="flex flex-col">
          <label className="text-sm font-medium text-slate-700 mb-1">
            {filter.label}
          </label>
          {filter.type === 'select' && (
            <select
              value={values[filter.key] || ''}
              onChange={(e) => handleChange(filter.key, e.target.value)}
              disabled={loading}
              className="px-3 py-2 border border-slate-300 rounded text-sm disabled:opacity-50"
            >
              <option value="">All</option>
              {filter.options?.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}
          {filter.type === 'date-range' && (
            <div className="flex gap-2">
              <input
                type="date"
                value={values[`${filter.key}_start`] || ''}
                onChange={(e) =>
                  handleChange(`${filter.key}_start`, e.target.value)
                }
                disabled={loading}
                className="px-3 py-2 border border-slate-300 rounded text-sm disabled:opacity-50"
              />
              <input
                type="date"
                value={values[`${filter.key}_end`] || ''}
                onChange={(e) =>
                  handleChange(`${filter.key}_end`, e.target.value)
                }
                disabled={loading}
                className="px-3 py-2 border border-slate-300 rounded text-sm disabled:opacity-50"
              />
            </div>
          )}
          {filter.type === 'search' && (
            <input
              type="text"
              placeholder={filter.placeholder || 'Search...'}
              value={values[filter.key] || ''}
              onChange={(e) => handleChange(filter.key, e.target.value)}
              disabled={loading}
              className="px-3 py-2 border border-slate-300 rounded text-sm disabled:opacity-50"
            />
          )}
          {filter.type === 'multi-select' && (
            <div className="flex flex-col gap-1">
              {filter.options?.map((opt) => (
                <label key={opt.value} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    value={opt.value}
                    checked={
                      values[filter.key]?.includes(opt.value) || false
                    }
                    onChange={(e) => {
                      const current = values[filter.key] || [];
                      const updated = e.target.checked
                        ? [...current, opt.value]
                        : current.filter((v: string) => v !== opt.value);
                      handleChange(filter.key, updated);
                    }}
                    disabled={loading}
                    className="disabled:opacity-50"
                  />
                  <span className="text-sm">{opt.label}</span>
                </label>
              ))}
            </div>
          )}
        </div>
      ))}
      <div className="flex gap-2 ml-auto">
        <button
          onClick={handleReset}
          disabled={loading}
          className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-50"
        >
          Reset
        </button>
        <button
          onClick={handleApply}
          disabled={loading}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          Apply
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd apps/console-web
npm test -- src/components/dashboard/__tests__/FilterBar.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/console-web/src/components/dashboard/FilterBar.tsx apps/console-web/src/components/dashboard/__tests__/FilterBar.test.tsx
git commit -m "feat(dashboard): add FilterBar component with tests"
```

---

## Task 4: Build ChartCard Component (console-web)

**Files:**
- Create: `apps/console-web/src/components/dashboard/ChartCard.tsx`
- Create: `apps/console-web/src/components/dashboard/__tests__/ChartCard.test.tsx`

**Interfaces:**
- Consumes: `ChartCardProps` from Task 1; Recharts components (BarChart, LineChart, PieChart, ComposedChart)
- Produces: `ChartCard` component exported as default

**Steps:**

- [ ] **Step 1: Write test for ChartCard**

Create `apps/console-web/src/components/dashboard/__tests__/ChartCard.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react';
import ChartCard from '../ChartCard';
import type { ChartCardProps } from '@/lib/types/dashboard';

// Mock Recharts to avoid rendering complexity in tests
jest.mock('recharts', () => ({
  ...jest.requireActual('recharts'),
  BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  PieChart: ({ children }: any) => <div data-testid="pie-chart">{children}</div>,
  ComposedChart: ({ children }: any) => (
    <div data-testid="composed-chart">{children}</div>
  ),
}));

describe('ChartCard', () => {
  const data = [
    { name: 'Jan', value: 10 },
    { name: 'Feb', value: 20 },
  ];

  it('renders title', () => {
    const props: ChartCardProps = {
      title: 'Test Chart',
      data,
      chartType: 'bar',
      xKey: 'name',
      yKey: 'value',
    };
    render(<ChartCard {...props} />);
    expect(screen.getByText('Test Chart')).toBeInTheDocument();
  });

  it('renders bar chart when chartType is bar', () => {
    const props: ChartCardProps = {
      title: 'Bar Chart',
      data,
      chartType: 'bar',
      xKey: 'name',
      yKey: 'value',
    };
    render(<ChartCard {...props} />);
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
  });

  it('renders line chart when chartType is line', () => {
    const props: ChartCardProps = {
      title: 'Line Chart',
      data,
      chartType: 'line',
      xKey: 'name',
      yKey: 'value',
    };
    render(<ChartCard {...props} />);
    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
  });

  it('renders pie chart when chartType is pie', () => {
    const props: ChartCardProps = {
      title: 'Pie Chart',
      data,
      chartType: 'pie',
    };
    render(<ChartCard {...props} />);
    expect(screen.getByTestId('pie-chart')).toBeInTheDocument();
  });

  it('renders loading skeleton when loading is true', () => {
    const props: ChartCardProps = {
      title: 'Loading',
      data: [],
      chartType: 'bar',
      loading: true,
    };
    const { container } = render(<ChartCard {...props} />);
    expect(container.querySelector('[data-testid="loading-skeleton"]')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd apps/console-web
npm test -- src/components/dashboard/__tests__/ChartCard.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement ChartCard component**

Create `apps/console-web/src/components/dashboard/ChartCard.tsx`:

```typescript
'use client';

import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  ComposedChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { ChartCardProps } from '@/lib/types/dashboard';

export default function ChartCard({
  title,
  data,
  chartType,
  xKey,
  yKey,
  series,
  height = 300,
  loading,
}: ChartCardProps) {
  if (loading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <div className="h-4 w-32 bg-slate-200 rounded mb-4" />
        <div
          data-testid="loading-skeleton"
          className="w-full bg-slate-100 rounded"
          style={{ height }}
        />
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6">
      <h3 className="text-lg font-semibold text-slate-900 mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={height}>
        {chartType === 'bar' && (
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={xKey} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey={yKey || 'value'} fill="#3b82f6" />
          </BarChart>
        )}
        {chartType === 'line' && (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={xKey} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line
              type="monotone"
              dataKey={yKey || 'value'}
              stroke="#3b82f6"
              dot={false}
            />
          </LineChart>
        )}
        {chartType === 'pie' && (
          <PieChart>
            <Pie
              data={data}
              dataKey={yKey || 'value'}
              nameKey={xKey || 'name'}
              cx="50%"
              cy="50%"
              outerRadius={80}
              fill="#3b82f6"
              label
            />
            <Tooltip />
          </PieChart>
        )}
        {chartType === 'composed' && (
          <ComposedChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={xKey} />
            <YAxis />
            <Tooltip />
            <Legend />
            {series?.map((s) => (
              <Bar key={s.key} dataKey={s.key} fill={s.fill} />
            ))}
          </ComposedChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd apps/console-web
npm test -- src/components/dashboard/__tests__/ChartCard.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/console-web/src/components/dashboard/ChartCard.tsx apps/console-web/src/components/dashboard/__tests__/ChartCard.test.tsx
git commit -m "feat(dashboard): add ChartCard component with Recharts integration"
```

---

## Task 5: Create Dashboard Layout & Navigation (console-web)

**Files:**
- Create: `apps/console-web/src/app/(console)/dashboard/layout.tsx`
- Create: `apps/console-web/src/components/dashboard/index.ts`

**Interfaces:**
- Consumes: Sidebar + Topbar from TASK-001
- Produces: Dashboard layout with sub-navigation to hr, admin, reports routes

**Steps:**

- [ ] **Step 1: Create component index**

Create `apps/console-web/src/components/dashboard/index.ts`:

```typescript
export { default as SummaryCard } from './SummaryCard';
export { default as FilterBar } from './FilterBar';
export { default as ChartCard } from './ChartCard';

export type { SummaryCardProps, FilterBarProps, ChartCardProps } from '@/lib/types/dashboard';
```

- [ ] **Step 2: Create dashboard layout**

Create `apps/console-web/src/app/(console)/dashboard/layout.tsx`:

```typescript
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  const tabs = [
    { label: 'HR Dashboard', href: '/dashboard/hr' },
    { label: 'Admin', href: '/dashboard/admin' },
    { label: 'Reports', href: '/dashboard/reports' },
  ];

  return (
    <div>
      {/* Tabs navigation */}
      <div className="border-b border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 py-4 flex gap-8">
          {tabs.map((tab) => {
            const isActive = pathname === tab.href;
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`text-sm font-medium transition-colors ${
                  isActive
                    ? 'border-b-2 border-blue-600 text-blue-600'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {tab.label}
              </Link>
            );
          })}
        </div>
      </div>

      {/* Dashboard content */}
      <div className="max-w-7xl mx-auto px-4 py-8">{children}</div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/console-web/src/components/dashboard/index.ts apps/console-web/src/app/\(console\)/dashboard/layout.tsx
git commit -m "feat(dashboard): add layout and component index"
```

---

## Task 6: Build HR Dashboard (console-web)

**Files:**
- Create: `apps/console-web/src/app/(console)/dashboard/hr/page.tsx`
- Create: `apps/console-web/src/app/(console)/dashboard/hr/__tests__/page.test.tsx`

**Interfaces:**
- Consumes: `SummaryCard`, `FilterBar`, `ChartCard`, API helpers from Task 1, `useAuth()` hook (from TASK-001)
- Produces: HR Dashboard page rendering KPIs + session table + trends

**Steps:**

- [ ] **Step 1: Write integration test for HR Dashboard**

Create `apps/console-web/src/app/(console)/dashboard/hr/__tests__/page.test.tsx`:

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import HRDashboard from '../page';

// Mock API calls
jest.mock('@/lib/api/dashboards', () => ({
  fetchHRDashboardCounts: jest.fn().mockResolvedValue({
    activeAssessments: 12,
    candidatesInProgress: 8,
    awaitingReview: 3,
    pendingDecisions: 2,
  }),
  fetchRecentSessions: jest.fn().mockResolvedValue([
    {
      id: '1',
      candidateName: 'Alice Chen',
      jobTitle: 'Senior Engineer',
      status: 'in_progress',
      startedAt: '2026-07-26T10:00:00Z',
      createdAt: '2026-07-25T10:00:00Z',
    },
  ]),
}));

// Mock useAuth hook
jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => ({ orgId: 'test-org' }),
}));

describe('HR Dashboard', () => {
  it('renders summary cards with counts', async () => {
    render(<HRDashboard />);
    await waitFor(() => {
      expect(screen.getByText('Active Assessments')).toBeInTheDocument();
      expect(screen.getByText('12')).toBeInTheDocument();
    });
  });

  it('renders recent sessions table', async () => {
    render(<HRDashboard />);
    await waitFor(() => {
      expect(screen.getByText('Alice Chen')).toBeInTheDocument();
      expect(screen.getByText('Senior Engineer')).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd apps/console-web
npm test -- src/app/\(console\)/dashboard/hr/__tests__/page.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement HR Dashboard**

Create `apps/console-web/src/app/(console)/dashboard/hr/page.tsx`:

```typescript
'use client';

import { useEffect, useState } from 'react';
import { SummaryCard, FilterBar, ChartCard } from '@/components/dashboard';
import { fetchHRDashboardCounts, fetchRecentSessions } from '@/lib/api/dashboards';
import { useAuth } from '@/lib/hooks/useAuth';
import type { DashboardSession, Filter, HRDashboardData } from '@/lib/types/dashboard';

export default function HRDashboard() {
  const { orgId } = useAuth();
  const [data, setData] = useState<HRDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>();

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const [counts, sessions] = await Promise.all([
          fetchHRDashboardCounts(orgId),
          fetchRecentSessions(orgId, statusFilter),
        ]);
        setData({
          ...counts,
          recentSessions: sessions,
        });
      } catch (error) {
        console.error('Failed to load HR dashboard:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [orgId, statusFilter]);

  const filters: Filter[] = [
    {
      key: 'status',
      label: 'Status',
      type: 'select',
      options: [
        { label: 'Invited', value: 'invited' },
        { label: 'In Progress', value: 'in_progress' },
        { label: 'Completed', value: 'completed' },
        { label: 'Expired', value: 'expired' },
      ],
    },
  ];

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold text-slate-900">HR Dashboard</h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard
          title="Active Assessments"
          value={data?.activeAssessments || 0}
          badge={{ label: 'Live', color: 'green' }}
          loading={loading}
        />
        <SummaryCard
          title="Candidates In Progress"
          value={data?.candidatesInProgress || 0}
          trend={{ value: data?.candidatesInProgress ? 2 : 0, direction: 'up' }}
          loading={loading}
        />
        <SummaryCard
          title="Awaiting Review"
          value={data?.awaitingReview || 0}
          badge={{ label: 'Action', color: 'amber' }}
          loading={loading}
        />
        <SummaryCard
          title="Pending Final Decision"
          value={data?.pendingDecisions || 0}
          loading={loading}
        />
      </div>

      {/* Filter Bar */}
      <FilterBar
        filters={filters}
        onApply={(values) => setStatusFilter(values.status)}
        onReset={() => setStatusFilter(undefined)}
        loading={loading}
      />

      {/* Recent Sessions Table */}
      <div className="rounded-lg border border-slate-200 bg-white">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">Recent Sessions</h2>
        </div>
        <table className="w-full">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Candidate
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Job
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Started
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {loading ? (
              <tr>
                <td colSpan={4} className="px-6 py-8 text-center text-slate-500">
                  Loading...
                </td>
              </tr>
            ) : data?.recentSessions && data.recentSessions.length > 0 ? (
              data.recentSessions.map((session) => (
                <tr key={session.id} className="hover:bg-slate-50">
                  <td className="px-6 py-4 text-sm text-slate-900">
                    {session.candidateName}
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">
                    {session.jobTitle}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    <span
                      className={`inline-block px-2 py-1 rounded text-xs font-semibold ${
                        session.status === 'in_progress'
                          ? 'bg-blue-100 text-blue-900'
                          : session.status === 'completed'
                          ? 'bg-green-100 text-green-900'
                          : 'bg-slate-100 text-slate-900'
                      }`}
                    >
                      {session.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">
                    {session.startedAt
                      ? new Date(session.startedAt).toLocaleDateString()
                      : '—'}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={4} className="px-6 py-8 text-center text-slate-500">
                  No sessions found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd apps/console-web
npm test -- src/app/\(console\)/dashboard/hr/__tests__/page.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/console-web/src/app/\(console\)/dashboard/hr/
git commit -m "feat(dashboard): add HR Dashboard with summary cards and session table"
```

---

## Task 7: Build Admin Dashboard (console-web)

**Files:**
- Create: `apps/console-web/src/app/(console)/dashboard/admin/page.tsx`
- Create: `apps/console-web/src/app/(console)/dashboard/admin/__tests__/page.test.tsx`

**Interfaces:**
- Consumes: `SummaryCard`, `fetchAdminDashboard` from Task 1
- Produces: Admin Dashboard page with user/competency/template tables

**Steps:**

- [ ] **Step 1: Write integration test**

Create `apps/console-web/src/app/(console)/dashboard/admin/__tests__/page.test.tsx`:

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import AdminDashboard from '../page';

jest.mock('@/lib/api/dashboards', () => ({
  fetchAdminDashboard: jest.fn().mockResolvedValue({
    totalUsers: 5,
    competencyCount: 24,
    templateCount: 4,
    users: [
      {
        id: '1',
        name: 'Srinivas',
        email: 's@fidelitus.com',
        role: 'admin',
        createdAt: '2026-01-01T00:00:00Z',
      },
    ],
    competencies: [
      {
        id: '1',
        name: 'Python',
        category: 'Technical',
        createdAt: '2026-01-01T00:00:00Z',
        entryCount: 12,
      },
    ],
    templates: [
      {
        id: '1',
        name: 'Senior Engineer',
        competencyCount: 5,
        createdAt: '2026-01-01T00:00:00Z',
      },
    ],
  }),
}));

jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => ({ orgId: 'test-org' }),
}));

describe('Admin Dashboard', () => {
  it('renders summary cards', async () => {
    render(<AdminDashboard />);
    await waitFor(() => {
      expect(screen.getByText('Total Users')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });
  });

  it('renders users table', async () => {
    render(<AdminDashboard />);
    await waitFor(() => {
      expect(screen.getByText('Srinivas')).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd apps/console-web
npm test -- src/app/\(console\)/dashboard/admin/__tests__/page.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement Admin Dashboard**

Create `apps/console-web/src/app/(console)/dashboard/admin/page.tsx`:

```typescript
'use client';

import { useEffect, useState } from 'react';
import { SummaryCard } from '@/components/dashboard';
import { fetchAdminDashboard } from '@/lib/api/dashboards';
import { useAuth } from '@/lib/hooks/useAuth';
import type { AdminDashboardData } from '@/lib/types/dashboard';

export default function AdminDashboard() {
  const { orgId } = useAuth();
  const [data, setData] = useState<AdminDashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const adminData = await fetchAdminDashboard(orgId);
        setData(adminData);
      } catch (error) {
        console.error('Failed to load admin dashboard:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [orgId]);

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold text-slate-900">Admin Dashboard</h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SummaryCard
          title="Total Users"
          value={data?.totalUsers || 0}
          loading={loading}
        />
        <SummaryCard
          title="Competency Entries"
          value={data?.competencyCount || 0}
          loading={loading}
        />
        <SummaryCard
          title="Role Templates"
          value={data?.templateCount || 0}
          loading={loading}
        />
      </div>

      {/* Users Table */}
      <div className="rounded-lg border border-slate-200 bg-white">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">Organization Users</h2>
        </div>
        <table className="w-full">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Email
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Role
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Joined
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {data?.users && data.users.length > 0 ? (
              data.users.map((user) => (
                <tr key={user.id} className="hover:bg-slate-50">
                  <td className="px-6 py-4 text-sm text-slate-900">{user.name}</td>
                  <td className="px-6 py-4 text-sm text-slate-600">{user.email}</td>
                  <td className="px-6 py-4 text-sm">
                    <span className="inline-block px-2 py-1 rounded text-xs font-semibold bg-blue-100 text-blue-900">
                      {user.role}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">
                    {new Date(user.createdAt).toLocaleDateString()}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={4} className="px-6 py-8 text-center text-slate-500">
                  No users found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Competencies Table */}
      <div className="rounded-lg border border-slate-200 bg-white">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">Competency Library</h2>
        </div>
        <table className="w-full">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Category
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Entries
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Created
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {data?.competencies && data.competencies.length > 0 ? (
              data.competencies.map((comp) => (
                <tr key={comp.id} className="hover:bg-slate-50">
                  <td className="px-6 py-4 text-sm text-slate-900">{comp.name}</td>
                  <td className="px-6 py-4 text-sm text-slate-600">{comp.category}</td>
                  <td className="px-6 py-4 text-sm text-slate-600">{comp.entryCount}</td>
                  <td className="px-6 py-4 text-sm text-slate-600">
                    {new Date(comp.createdAt).toLocaleDateString()}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={4} className="px-6 py-8 text-center text-slate-500">
                  No competencies found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Templates Table */}
      <div className="rounded-lg border border-slate-200 bg-white">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">Role Templates</h2>
        </div>
        <table className="w-full">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Competencies
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Created
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {data?.templates && data.templates.length > 0 ? (
              data.templates.map((template) => (
                <tr key={template.id} className="hover:bg-slate-50">
                  <td className="px-6 py-4 text-sm text-slate-900">
                    {template.name}
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">
                    {template.competencyCount}
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">
                    {new Date(template.createdAt).toLocaleDateString()}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={3} className="px-6 py-8 text-center text-slate-500">
                  No templates found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd apps/console-web
npm test -- src/app/\(console\)/dashboard/admin/__tests__/page.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/console-web/src/app/\(console\)/dashboard/admin/
git commit -m "feat(dashboard): add Admin Dashboard with user, competency, and template tables"
```

---

## Task 8: Build Reports Dashboard (console-web)

**Files:**
- Create: `apps/console-web/src/app/(console)/dashboard/reports/page.tsx`
- Create: `apps/console-web/src/app/(console)/dashboard/reports/__tests__/page.test.tsx`

**Interfaces:**
- Consumes: `SummaryCard`, `FilterBar`, `ChartCard`, `fetchReportsList` from Task 1
- Produces: Reports Dashboard with filterable table, charts, and pagination

**Steps:**

- [ ] **Step 1: Write integration test**

Create `apps/console-web/src/app/(console)/dashboard/reports/__tests__/page.test.tsx`:

```typescript
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import ReportsDashboard from '../page';

jest.mock('@/lib/api/dashboards', () => ({
  fetchReportsList: jest.fn().mockResolvedValue({
    reports: [
      {
        id: '1',
        candidateName: 'Alice Chen',
        jobTitle: 'Senior Engineer',
        verdict: 'strong_hire',
        overallScore: 4.62,
        createdAt: '2026-07-26T00:00:00Z',
      },
    ],
    verdictDistribution: [
      { verdict: 'strong_hire', count: 5 },
      { verdict: 'hire', count: 3 },
    ],
    scoreBandDistribution: [
      { band: '4.5-5.0', count: 8 },
      { band: '3.5-4.4', count: 5 },
    ],
    totalCount: 42,
    currentPage: 0,
    pageSize: 20,
  }),
}));

jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => ({ orgId: 'test-org' }),
}));

describe('Reports Dashboard', () => {
  it('renders filter bar', async () => {
    render(<ReportsDashboard />);
    expect(screen.getByText('Apply')).toBeInTheDocument();
  });

  it('renders charts', async () => {
    render(<ReportsDashboard />);
    await waitFor(() => {
      expect(screen.getByText('Verdict Distribution')).toBeInTheDocument();
    });
  });

  it('renders reports table', async () => {
    render(<ReportsDashboard />);
    await waitFor(() => {
      expect(screen.getByText('Alice Chen')).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd apps/console-web
npm test -- src/app/\(console\)/dashboard/reports/__tests__/page.test.tsx
```

Expected: FAIL.

- [ ] **Step 3: Implement Reports Dashboard**

Create `apps/console-web/src/app/(console)/dashboard/reports/page.tsx`:

```typescript
'use client';

import { useEffect, useState } from 'react';
import { SummaryCard, FilterBar, ChartCard } from '@/components/dashboard';
import { fetchReportsList } from '@/lib/api/dashboards';
import { useAuth } from '@/lib/hooks/useAuth';
import type { Filter, ReportsDashboardData } from '@/lib/types/dashboard';

export default function ReportsDashboard() {
  const { orgId } = useAuth();
  const [data, setData] = useState<ReportsDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    verdicts: [] as string[],
    scoreBands: [] as string[],
  });
  const [page, setPage] = useState(0);
  const pageSize = 20;

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const reportData = await fetchReportsList(
          orgId,
          filters,
          pageSize,
          page * pageSize
        );
        setData(reportData);
      } catch (error) {
        console.error('Failed to load reports:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [orgId, filters, page]);

  const filterDefinitions: Filter[] = [
    {
      key: 'verdicts',
      label: 'Verdict',
      type: 'multi-select',
      options: [
        { label: 'Strong Hire', value: 'strong_hire' },
        { label: 'Hire', value: 'hire' },
        { label: 'Consider', value: 'consider' },
        { label: 'Borderline', value: 'borderline' },
        { label: 'Reject', value: 'reject' },
      ],
    },
    {
      key: 'scoreBands',
      label: 'Score Band',
      type: 'multi-select',
      options: [
        { label: '4.5 – 5.0', value: '4.5-5.0' },
        { label: '4.0 – 4.4', value: '4.0-4.4' },
        { label: '3.5 – 3.9', value: '3.5-3.9' },
        { label: '3.0 – 3.4', value: '3.0-3.4' },
        { label: '< 3.0', value: '<3.0' },
      ],
    },
    {
      key: 'startDate',
      label: 'Date Range',
      type: 'date-range',
    },
  ];

  const handleFilterApply = (values: Record<string, any>) => {
    setFilters({
      verdicts: values.verdicts || [],
      scoreBands: values.scoreBands || [],
    });
    setPage(0);
  };

  const handleFilterReset = () => {
    setFilters({
      verdicts: [],
      scoreBands: [],
    });
    setPage(0);
  };

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold text-slate-900">Reports Dashboard</h1>

      {/* Filter Bar */}
      <FilterBar
        filters={filterDefinitions}
        onApply={handleFilterApply}
        onReset={handleFilterReset}
        loading={loading}
      />

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard
          title="Verdict Distribution"
          data={data?.verdictDistribution || []}
          chartType="pie"
          xKey="verdict"
          yKey="count"
          loading={loading}
          height={300}
        />
        <ChartCard
          title="Score Band Distribution"
          data={data?.scoreBandDistribution || []}
          chartType="bar"
          xKey="band"
          yKey="count"
          loading={loading}
          height={300}
        />
      </div>

      {/* Reports Table */}
      <div className="rounded-lg border border-slate-200 bg-white">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">Hiring Reports</h2>
        </div>
        <table className="w-full">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Candidate
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Job
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Verdict
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Score
              </th>
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-900">
                Created
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                  Loading...
                </td>
              </tr>
            ) : data?.reports && data.reports.length > 0 ? (
              data.reports.map((report) => (
                <tr key={report.id} className="hover:bg-slate-50">
                  <td className="px-6 py-4 text-sm text-slate-900">
                    {report.candidateName}
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">
                    {report.jobTitle}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    <span
                      className={`inline-block px-2 py-1 rounded text-xs font-semibold ${
                        report.verdict === 'strong_hire'
                          ? 'bg-green-100 text-green-900'
                          : report.verdict === 'hire'
                          ? 'bg-blue-100 text-blue-900'
                          : report.verdict === 'consider'
                          ? 'bg-amber-100 text-amber-900'
                          : 'bg-slate-100 text-slate-900'
                      }`}
                    >
                      {report.verdict.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-900 font-mono">
                    {report.overallScore.toFixed(2)}
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">
                    {new Date(report.createdAt).toLocaleDateString()}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                  No reports found
                </td>
              </tr>
            )}
          </tbody>
        </table>

        {/* Pagination */}
        <div className="px-6 py-4 border-t border-slate-200 flex justify-between items-center">
          <p className="text-sm text-slate-600">
            Showing {page * pageSize + 1} – {Math.min((page + 1) * pageSize, data?.totalCount || 0)} of{' '}
            {data?.totalCount || 0}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0 || loading}
              className="px-3 py-1 text-sm border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-50"
            >
              ← Prev
            </button>
            <button
              onClick={() =>
                setPage(
                  data ? Math.floor(data.totalCount / pageSize) : page + 1
                )
              }
              disabled={!data || (page + 1) * pageSize >= data.totalCount || loading}
              className="px-3 py-1 text-sm border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-50"
            >
              Next →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd apps/console-web
npm test -- src/app/\(console\)/dashboard/reports/__tests__/page.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/console-web/src/app/\(console\)/dashboard/reports/
git commit -m "feat(dashboard): add Reports Dashboard with filters, charts, and pagination"
```

---

## Task 9: Setup Types & API Helpers (candidate-web)

**Files:**
- Create: `apps/candidate-web/src/lib/types/dashboard.ts`
- Create: `apps/candidate-web/src/lib/api/status.ts`

**Interfaces:**
- Produces: Status page types; API helper to fetch session data (already loaded via SessionContext)

**Steps:**

- [ ] **Step 1: Create dashboard types**

Create `apps/candidate-web/src/lib/types/dashboard.ts`:

```typescript
// Candidate status view types
export interface CandidateStatusProps {
  jobTitle: string;
  companyName: string;
  sessionState: 'invited' | 'in_progress' | 'completed' | 'expired';
  startedAt?: string;
  completedAt?: string;
  durationMinutes?: number;
  nextSteps?: string;
}

export interface InterviewDetails {
  format?: 'video' | 'phone' | 'in_person';
  duration?: number;
  scheduledAt?: string;
}
```

- [ ] **Step 2: Create API helpers**

Create `apps/candidate-web/src/lib/api/status.ts`:

```typescript
// Status page uses SessionContext for all data
// This file contains formatting helpers only
export function getStatusBadge(
  state: 'invited' | 'in_progress' | 'completed' | 'expired'
): { label: string; color: string } {
  switch (state) {
    case 'invited':
      return { label: 'Not Started', color: 'blue' };
    case 'in_progress':
      return { label: 'In Progress', color: 'blue' };
    case 'completed':
      return { label: 'Under Review', color: 'amber' };
    case 'expired':
      return { label: 'Expired', color: 'red' };
  }
}

export function getDaysElapsed(startedAt?: string): number | null {
  if (!startedAt) return null;
  const now = new Date();
  const started = new Date(startedAt);
  const diffMs = now.getTime() - started.getTime();
  return Math.floor(diffMs / (1000 * 60 * 60 * 24));
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/candidate-web/src/lib/types/dashboard.ts apps/candidate-web/src/lib/api/status.ts
git commit -m "feat(status): add types and helpers for candidate status page"
```

---

## Task 10: Build Candidate Dashboard / Status Page (candidate-web)

**Files:**
- Create or modify: `apps/candidate-web/src/app/status/page.tsx`
- Create: `apps/candidate-web/src/app/status/__tests__/page.test.tsx`

**Interfaces:**
- Consumes: `SessionContext` from TASK-001, `useSession()` hook, status API helpers
- Produces: Status page rendering job title, session state, next steps (NO scores)

**Critical Security:** This page must NEVER render any of: raw scores, competency evaluations, behavioral profiles, integrity flags, salary band, AI confidence score, internal recommendation text.

**Steps:**

- [ ] **Step 1: Write security test**

Create `apps/candidate-web/src/app/status/__tests__/page.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react';
import StatusPage from '../page';

// Mock SessionContext to provide session data
jest.mock('@/context/SessionContext', () => ({
  useSession: () => ({
    session: {
      id: 'test-session',
      jobTitle: 'Senior Engineer',
      jobCompany: 'Fidelitus Corp',
      status: 'completed',
      startedAt: '2026-07-26T10:00:00Z',
      completedAt: '2026-07-26T11:00:00Z',
      durationMinutes: 45,
      // Critically: no scores in this context
    },
  }),
}));

describe('Candidate Status Page', () => {
  it('renders job title', () => {
    render(<StatusPage />);
    expect(screen.getByText('Senior Engineer')).toBeInTheDocument();
  });

  it('renders company name', () => {
    render(<StatusPage />);
    expect(screen.getByText('Fidelitus Corp')).toBeInTheDocument();
  });

  it('renders status badge', () => {
    render(<StatusPage />);
    expect(screen.getByText('Under Review')).toBeInTheDocument();
  });

  it('does NOT render any raw scores or confidence metrics', () => {
    const { container } = render(<StatusPage />);
    const text = container.textContent || '';
    // Check that no score-like numbers appear
    expect(text).not.toMatch(/^\d\.\d{2}$/m);
    expect(text).not.toMatch(/confidence/i);
    expect(text).not.toMatch(/score/i);
  });
});
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd apps/candidate-web
npm test -- src/app/status/__tests__/page.test.tsx
```

Expected: FAIL (page doesn't exist yet).

- [ ] **Step 3: Implement Status Page**

Create `apps/candidate-web/src/app/status/page.tsx`:

```typescript
'use client';

import { useSession } from '@/context/SessionContext';
import { getStatusBadge, getDaysElapsed } from '@/lib/api/status';

const badgeColorMap = {
  blue: 'bg-blue-100 text-blue-900',
  amber: 'bg-amber-100 text-amber-900',
  red: 'bg-red-100 text-red-900',
};

export default function StatusPage() {
  const { session } = useSession();

  if (!session) {
    return (
      <div id="main-content" className="min-h-screen bg-white p-6">
        <div className="max-w-2xl mx-auto text-center">
          <p className="text-slate-600">Loading status...</p>
        </div>
      </div>
    );
  }

  const badge = getStatusBadge(session.status);
  const daysElapsed = getDaysElapsed(session.startedAt);

  return (
    <div id="main-content" className="min-h-screen bg-slate-50">
      <div className="max-w-2xl mx-auto px-4 py-12">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Your Status</h1>
          <p className="text-slate-600">Assessment progress and next steps</p>
        </div>

        {/* Assessment Info Card */}
        <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
          <div className="space-y-4">
            <div>
              <p className="text-sm font-medium text-slate-600">Assessment</p>
              <p className="text-lg font-semibold text-slate-900">
                {session.jobTitle || 'Assessment'}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-slate-600">Company</p>
              <p className="text-lg font-semibold text-slate-900">
                {session.jobCompany || 'Fidelitus Corp'}
              </p>
            </div>
          </div>
        </div>

        {/* Status Card */}
        <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">Current Status</p>
              <p className="text-sm text-slate-600 mt-1">
                {session.status === 'invited' && 'Your assessment is ready. Click below to begin.'}
                {session.status === 'in_progress' && `You started ${daysElapsed} day${daysElapsed !== 1 ? 's' : ''} ago.`}
                {session.status === 'completed' && 'Your assessment has been submitted.'}
                {session.status === 'expired' && 'Your assessment link has expired.'}
              </p>
            </div>
            <span
              className={`inline-block px-3 py-1 rounded-full text-sm font-semibold ${
                badgeColorMap[badge.color as keyof typeof badgeColorMap]
              }`}
            >
              {badge.label}
            </span>
          </div>
        </div>

        {/* Next Steps */}
        <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">What's Next</h2>
          {session.status === 'completed' ? (
            <div className="space-y-3 text-sm text-slate-700">
              <p>
                Thank you for completing your assessment. Our hiring team is reviewing your responses.
              </p>
              <p>
                Expect a decision within <strong>5–7 business days</strong>.
              </p>
              <p>
                We'll send an email update to <strong>{session.candidateEmail || 'your email'}</strong>.
              </p>
            </div>
          ) : session.status === 'in_progress' ? (
            <div className="space-y-3 text-sm text-slate-700">
              <p>
                You're making great progress! Continue answering the remaining questions.
              </p>
              <p>
                Time available: <strong>{session.durationMinutes || 45} minutes</strong>
              </p>
              <p className="text-slate-600">
                <a href="/assessment" className="text-blue-600 hover:underline">
                  Return to assessment →
                </a>
              </p>
            </div>
          ) : session.status === 'invited' ? (
            <div className="space-y-3 text-sm text-slate-700">
              <p>
                Your assessment is ready to begin. You'll have{' '}
                <strong>{session.durationMinutes || 45} minutes</strong> to complete it.
              </p>
              <p className="text-slate-600">
                <a href="/assessment" className="text-blue-600 hover:underline">
                  Start assessment →
                </a>
              </p>
            </div>
          ) : (
            <p className="text-sm text-slate-700">
              Your assessment link has expired. Please contact the hiring team for a new link.
            </p>
          )}
        </div>

        {/* Interview Details (if applicable) */}
        {session.interviewFormat && (
          <div className="bg-white rounded-lg border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">
              Interview Details
            </h2>
            <div className="space-y-3 text-sm">
              <div>
                <p className="font-medium text-slate-600">Format</p>
                <p className="text-slate-900 capitalize">
                  {session.interviewFormat}
                </p>
              </div>
              {session.durationMinutes && (
                <div>
                  <p className="font-medium text-slate-600">Duration</p>
                  <p className="text-slate-900">{session.durationMinutes} minutes</p>
                </div>
              )}
              {!session.scheduledAt && (
                <p className="text-slate-600 italic">
                  Interview details will appear once scheduled.
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd apps/candidate-web
npm test -- src/app/status/__tests__/page.test.tsx
```

Expected: PASS. **Critical:** Verify security test passes (no raw scores rendered).

- [ ] **Step 5: Commit**

```bash
git add apps/candidate-web/src/app/status/
git commit -m "feat(status): add candidate status page with security guards (no scores exposed)"
```

---

## Task 11: Visual Testing & Cross-Browser Verification

**Files:**
- No new files; visual inspection of all four dashboards in browser

**Steps:**

- [ ] **Step 1: Start console-web dev server**

```bash
cd apps/console-web
npm run dev
```

Navigate to `http://localhost:3002/dashboard/hr`.

- [ ] **Step 2: Verify HR Dashboard**

- [ ] Summary cards render with correct values
- [ ] Filter bar works (can change status, see table update)
- [ ] Recent sessions table shows data
- [ ] Verify light mode and dark mode (if Tailwind dark class enabled)
- [ ] Verify WCAG focus rings on buttons (Tab key)

- [ ] **Step 3: Verify Admin Dashboard**

Navigate to `http://localhost:3002/dashboard/admin`.

- [ ] Summary cards render (Total Users, Competencies, Templates)
- [ ] User table renders
- [ ] Competency table renders
- [ ] Template table renders
- [ ] All tables are sortable/interactive

- [ ] **Step 4: Verify Reports Dashboard**

Navigate to `http://localhost:3002/dashboard/reports`.

- [ ] Filter bar renders with Verdict, Score Band, Date Range
- [ ] Charts render (pie and bar)
- [ ] Reports table renders with pagination
- [ ] Pagination controls work
- [ ] Verify scores are visible (this is HR view, not candidate)

- [ ] **Step 5: Start candidate-web dev server**

In a new terminal:

```bash
cd apps/candidate-web
npm run dev
```

Navigate to `http://localhost:3000/status` (requires valid session token in URL or SessionContext).

- [ ] **Step 6: Verify Candidate Status Page**

- [ ] Job title + company display correctly
- [ ] Status badge shows correct label and color
- [ ] No raw scores visible anywhere on page
- [ ] Search page source (Ctrl+F) for: "confidence", "score", "salary", "recommendation" — all should be absent
- [ ] Next steps text is appropriate for each status (invited/in_progress/completed/expired)
- [ ] Verify WCAG focus rings on links

- [ ] **Step 7: Commit visual testing notes**

```bash
git add .
git commit -m "test(dashboard): verify all dashboards render correctly, candidate view score-safe"
```

---

## Task 12: Integration & Type Checking

**Files:**
- No new files; verification only

**Steps:**

- [ ] **Step 1: Run TypeScript strict type-check on console-web**

```bash
cd apps/console-web
npx tsc --noEmit
```

Expected: PASS (no errors).

- [ ] **Step 2: Run TypeScript strict type-check on candidate-web**

```bash
cd apps/candidate-web
npx tsc --noEmit
```

Expected: PASS (no errors).

- [ ] **Step 3: Run all dashboard tests**

```bash
cd apps/console-web
npm test -- src/components/dashboard
npm test -- src/app/\(console\)/dashboard
```

Expected: All tests PASS.

```bash
cd apps/candidate-web
npm test -- src/app/status
```

Expected: All tests PASS.

- [ ] **Step 4: Lint both apps**

```bash
cd apps/console-web
npm run lint

cd apps/candidate-web
npm run lint
```

Expected: No errors.

- [ ] **Step 5: Commit final integration results**

```bash
git add .
git commit -m "test(dashboard): all type checks, lints, and tests pass"
```

---

## Success Checklist (Exit Criteria)

- [ ] SummaryCard, FilterBar, ChartCard components all render with correct props
- [ ] HR Dashboard loads active/in-progress/awaiting-review/pending counts from API
- [ ] HR Dashboard filters by status, renders Recent Sessions table, quick-link navigation works
- [ ] Admin Dashboard renders User, Competency, Template tables with live data
- [ ] Reports Dashboard renders filterable, paginated list; verdicts + score-band filters work
- [ ] Reports Dashboard shows verdict distribution (pie) + score-band distribution (bar)
- [ ] Candidate Status page loads from SessionContext, exposes only job title + status (no scores)
- [ ] All four dashboards visually verified in browser (light + dark mode)
- [ ] TypeScript strict mode: all pages pass type-check
- [ ] All tests passing (unit + integration)
- [ ] Accessibility: WCAG 2.1 AA focus rings on all interactive elements
- [ ] Security: no raw scores in candidate views (network inspection + source code search)

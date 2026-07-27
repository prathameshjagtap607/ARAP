# M10 Dashboards — Design Spec
**Date:** 2026-07-27  
**PRD ref:** §16 Phase 5 (M10 F01–F04)  
**Task:** TASK-005 (Phase 5)  
**Module scope:** `apps/console-web/src/app/(console)/dashboard/` + `apps/candidate-web/src/app/status/` ONLY

---

## Objective

Build four role-scoped dashboards that surface hiring pipeline state, candidate progress, org administration, and hiring report archive. Reuse a single set of shared components (SummaryCard, FilterBar, ChartCard) across all four to maintain consistency and reduce duplication. **Critical:** Candidate view must never expose raw scores or internal evaluation data.

---

## File Layout

```
apps/console-web/
  src/
    components/dashboard/
      SummaryCard.tsx        # KPI tile: count/value + badge + optional trend
      FilterBar.tsx          # Org-scoped filters: date, status, verdict, score-band
      ChartCard.tsx          # Recharts wrapper (bar/line/pie)
      index.ts               # Re-export all three
    app/(console)/
      dashboard/
        layout.tsx           # Sidebar nav linking to 3 sub-dashboards
        hr/
          page.tsx           # M10-F01 HR Dashboard
        admin/
          page.tsx           # M10-F03 Admin Dashboard
        reports/
          page.tsx           # M10-F04 Reports Dashboard

apps/candidate-web/
  src/
    components/dashboard/
      (identical structure to console-web's dashboard components)
    app/
      status/
        layout.tsx           # Candidate status page layout
        page.tsx             # M10-F02 Candidate Dashboard (Status)

services/orchestrator-api/
  src/modules/
    (no new modules — existing endpoints in assessments, candidates, reports, 
     competency_library, users suffice)
```

---

## Shared Components

### 1. SummaryCard

**Purpose:** Display a single KPI (active assessment count, pending decisions, etc.) with optional status badge and trend.

**Props:**
```typescript
interface SummaryCardProps {
  title: string;
  value: string | number;
  badge?: { label: string; color: 'amber' | 'green' | 'red' | 'blue' };
  icon?: React.ReactNode;
  trend?: { value: number; direction: 'up' | 'down' | 'flat' };
  onClick?: () => void;
  loading?: boolean;
}
```

**Rendering:**
- Large, centered value (e.g., "12")
- Title below
- Optional badge (e.g., "Active")
- Optional trend sparkline or arrow
- Clickable if `onClick` provided
- Loading skeleton if `loading: true`

**Used by:**
- HR Dashboard: "Active Assessments" (12), "Candidates In Progress" (8), "Awaiting Review" (3), "Pending Decisions" (2)
- Admin Dashboard: "Total Users" (5), "Competency Entries" (24), "Role Templates" (4)
- Candidate Dashboard: None (candidate uses text status only)

---

### 2. FilterBar

**Purpose:** Collect and apply filters for tabular/searchable views.

**Props:**
```typescript
interface FilterBarProps {
  filters: Filter[];
  onApply: (filters: Record<string, any>) => void;
  onReset: () => void;
  loading?: boolean;
}

interface Filter {
  key: string;
  label: string;
  type: 'date-range' | 'select' | 'search' | 'multi-select';
  options?: { label: string; value: string }[];
  placeholder?: string;
}
```

**Rendering:**
- Horizontal row of input fields (date pickers, dropdowns, search boxes)
- "Apply" and "Reset" buttons
- Org-scoped: all queries respect `claims.org_id` from JWT

**Used by:**
- HR Dashboard: Status filter (invited/in_progress/completed), date range
- Reports Dashboard: Verdict filter (strong_hire/hire/consider/borderline/reject), score-band filter (4.0–5.0 / 3.0–4.0 / etc.), date range, search by candidate name
- Admin Dashboard: User type filter (admin/user), role filter
- Candidate Dashboard: None (single-candidate view, no filtering)

---

### 3. ChartCard

**Purpose:** Render Recharts graphs with consistent styling and responsive behavior.

**Props:**
```typescript
interface ChartCardProps {
  title: string;
  data: any[];
  chartType: 'bar' | 'line' | 'pie' | 'composed';
  xKey?: string;
  yKey?: string;
  series?: { key: string; fill: string }[];
  height?: number;
  loading?: boolean;
}
```

**Rendering:**
- Card wrapper with title
- Recharts component (bar/line/pie) filling the container
- Responsive to viewport width (mobile: single-column, desktop: multi-column grid)
- Loading skeleton if `loading: true`

**Used by:**
- HR Dashboard: Session completion trend (line), competency distribution (bar)
- Reports Dashboard: Verdict distribution (pie), score band distribution (bar)
- Admin Dashboard: User activity timeline (line)
- Analytics views (M11, deferred): score trends, funnel, benchmarking

---

## Dashboard Designs

### M10-F01: HR Dashboard (`console-web/src/app/(console)/dashboard/hr/page.tsx`)

**Access:** `require_user` role (User or Admin)

**Layout (desktop):**
```
┌─────────────────────────────────────────────────────────┐
│  HR Dashboard                                           │
├─────────────────────────────────────────────────────────┤
│  [Status Filter ▼] [Date Range ▼] [Apply] [Reset]      │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Active       │  │ In Progress  │  │ Awaiting     │  │
│  │ Assessments  │  │ Candidates   │  │ Review      │  │
│  │     12       │  │      8       │  │      3      │  │
│  │ [+2 trend]   │  │ [-1 trend]   │  │ [→ flat]    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│  ┌──────────────┐                                      │
│  │ Pending      │                                      │
│  │ Final Decis. │                                      │
│  │      2       │                                      │
│  │ [→ flat]     │                                      │
│  └──────────────┘                                      │
├─────────────────────────────────────────────────────────┤
│  Recent Sessions (table)                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Candidate   | Job      | Status  | Started | ↗  │   │
│  │ Alice Chen  | Senior   | In Prog | 2d ago  | ... │   │
│  │ Bob Smith   | Engineer | Review  | 1d ago  | ... │   │
│  │ ...                                                │   │
│  └─────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  Session Completion Trend (line chart)                 │
│  [Chart spanning full width]                           │
└─────────────────────────────────────────────────────────┘
```

**API calls:**
- `GET /assessments?org_id=X&active=true` → active count
- `GET /sessions?org_id=X&status=in_progress` → in-progress count
- `GET /reports?org_id=X&status=awaiting_review` → awaiting-review count
- `GET /reports?org_id=X&status=pending_decision` → pending-decision count
- `GET /sessions?org_id=X&limit=10&offset=0&status=<filter>` → table rows
- `GET /analytics/sessions/completion-trend?org_id=X&start_date=&end_date=` → chart data

**Quick-link behavior:**
- Clicking a SummaryCard number filters the Recent Sessions table below it by that status
- Clicking a row in Recent Sessions table navigates to `/dashboard/reports/[sessionId]` (report detail view)

**Data refresh:** On-load + manual Apply filter

---

### M10-F02: Candidate Dashboard (`candidate-web/src/app/status/page.tsx`)

**Access:** Candidate JWT only (no organization context in JWT)

**Layout (mobile-first, single-column):**
```
┌──────────────────────────────┐
│  Your Status                 │
├──────────────────────────────┤
│  Assessment: Senior Engineer │
│  Company: Fidelitus Corp     │
├──────────────────────────────┤
│  Status: Under Review  [🟡]  │
│  (Waiting for recruiter)     │
├──────────────────────────────┤
│  What's Next                 │
│  Expect a decision within    │
│  5–7 business days.          │
│  We'll email you at:         │
│  alice@example.com           │
├──────────────────────────────┤
│  Interview Details           │
│  Format: Video               │
│  Duration: 45 minutes        │
│  (Not yet scheduled)         │
├──────────────────────────────┤
│  [Back to candidates]        │
└──────────────────────────────┘
```

**Data source:** `SessionContext` (loaded at session start via `GET /sessions/{sessionId}`)

**Never exposed:**
- Raw scores or confidence percentages
- Competency evaluations
- Behavioral profiles
- Integrity flags
- Salary band
- AI confidence score
- Internal recommendation text

**Fields exposed (if available):**
- `job_assessments.title` (job title)
- `job_assessments.interview_format` (video/phone/in-person, if applicable in M10)
- `sessions.duration_minutes` (if set)
- `sessions.started_at` → "In Progress for X days"
- `sessions.completed_at` → "Submitted on [date]"
- `hiring_reports.status` → "Under Review" badge (amber)

**Data refresh:** On-load only (candidate has no reason to refresh; status is pushed via email when ready)

---

### M10-F03: Admin Dashboard (`console-web/src/app/(console)/dashboard/admin/page.tsx`)

**Access:** `require_admin` role only

**Layout (desktop):**
```
┌─────────────────────────────────────────────────────────┐
│  Admin Dashboard                                        │
├─────────────────────────────────────────────────────────┤
│  [User Type ▼] [Role ▼] [Apply] [Reset]                │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Total Users  │  │ Competency   │  │ Role Templ.  │  │
│  │      5       │  │ Entries      │  │      4       │  │
│  │ [→ flat]     │  │      24      │  │ [→ flat]     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────┤
│  Organization Users (table)                             │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Name     | Email        | Role  | Joined | Actn│   │
│  │ Srinivas | s@fidelitus  | Admin | 1/1   | ✎ ✕ │   │
│  │ Alice    | a@fidelitus  | User  | 1/15  | ✎ ✕ │   │
│  │ ...                                               │   │
│  └─────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  Competency Library (table)                             │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Name           | Category | Created | Entries   │   │
│  │ Python         | Technical| 1/1     | 12        │   │
│  │ Leadership     | Soft     | 1/10    | 8         │   │
│  │ ...                                               │   │
│  └─────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  Role Templates (table, collapsed view)                │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Name                 | Competencies | Created   │   │
│  │ Senior Engineer      | 5            | 1/5       │   │
│  │ Product Manager      | 7            | 1/8       │   │
│  │ ...                                               │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**API calls:**
- `GET /users?org_id=X` → user table
- `GET /competency-library?org_id=X` → competency entries
- `GET /role-templates?org_id=X` → templates

**Permissions:**
- Add/Edit/Delete users: `require_admin`
- Add/Edit competencies: `require_user` (org users can manage library)
- Add/Edit templates: `require_user`

**Note:** User management (add/edit/delete) and competency library CRUD already built in TASK-001. This dashboard is a read-heavy view; edit flows already exist as modal forms or separate pages.

**Billing/plan status (M10-F03 requirement):**
- Deferred if no billing system built yet (stub placeholder or TODO comment)
- Add section when billing module ships (separate milestone)

---

### M10-F04: Reports Dashboard (`console-web/src/app/(console)/dashboard/reports/page.tsx`)

**Access:** `require_user` role

**Layout (desktop):**
```
┌─────────────────────────────────────────────────────────┐
│  Reports Dashboard                                      │
├─────────────────────────────────────────────────────────┤
│  [Verdict ▼] [Score Band ▼] [Date Range ▼] [Search...]│
│  [Apply] [Reset]                                        │
├─────────────────────────────────────────────────────────┤
│  Verdict Distribution (pie)  | Score Band (bar)         │
│  [Pie Chart]                  | [Bar Chart]             │
├─────────────────────────────────────────────────────────┤
│  Hiring Reports (searchable table)                      │
│  ┌────────────────────────────────────────────────┐    │
│  │ Candidate | Job | Verdict | Score | Created   │    │
│  │ Alice C.  | SE  | Strong  | 4.62  | 2d ago    │    │
│  │           |     | Hire    |       | [View PDF]│    │
│  │ Bob S.    | PM  | Consider| 3.15  | 3d ago    │    │
│  │           |     |         |       | [View PDF]│    │
│  │ ...                                             │    │
│  └────────────────────────────────────────────────┘    │
│  Showing 1–20 of 42        [< Prev] [1 2 3] [Next >] │
└─────────────────────────────────────────────────────────┘
```

**API calls:**
- `GET /reports?org_id=X&status=completed&filters=...` → paginated list
- `GET /reports/{session_id}/full` → full report JSON (if clicking "View")
- `GET /reports/{session_id}/pdf` → PDF download

**Filters:**
- Verdict: strong_hire, hire, consider, borderline, reject (multi-select)
- Score band: 4.5–5.0, 4.0–4.4, 3.5–3.9, 3.0–3.4, <3.0 (multi-select)
- Date range: start_date, end_date
- Search: candidate name, job title (full-text or substring)

**Pagination:**
- Default limit: 20 per page
- State maintained in URL query params (`?limit=20&offset=0&verdict=...`)

**Scoring note:**
- "Score" column shows `overall` from `hiring_reports.score_rollup` (visible only to org users, not candidates)
- Never exposed via shared link (`GET /reports/shared/{token}`)

---

## Data Flow & API Contracts

All existing endpoints suffice; no new backend endpoints required:

| Dashboard | Feature | Existing Endpoint |
|-----------|---------|-------------------|
| HR | Active assessments | `GET /assessments?active=true` |
| HR | Session list | `GET /sessions?status=in_progress&limit=10` |
| HR | Session completion trend | `GET /analytics/sessions/completion-trend?start=&end=` (new, M11) |
| Admin | Users | `GET /users?org_id=X` |
| Admin | Competencies | `GET /competency-library?org_id=X` |
| Admin | Templates | `GET /role-templates?org_id=X` |
| Reports | Reports list | `GET /reports?org_id=X&status=completed` |
| Reports | Report detail | `GET /reports/{session_id}/full` (existing, M9) |
| Reports | PDF | `GET /reports/{session_id}/pdf` (existing, M9) |
| Candidate | Session data | `GET /sessions/{session_id}` (existing, M5) |

**New Analytics endpoints (deferred to M11, but design for them now):**
- `GET /analytics/sessions/completion-trend?org_id=X&start_date=...&end_date=...` → `[{ date, count }]`
- `GET /analytics/verdict-distribution?org_id=X` → `[{ verdict, count }]`
- `GET /analytics/score-band-distribution?org_id=X` → `[{ band, count }]`

---

## Security & Role-Based Visibility

### Candidate View (candidate-web)
- JWT: candidate-scoped, no org_id
- **Never exposed:** raw scores, competency evaluations, behavioral profiles, integrity flags, salary, AI confidence, recommendation text, internal notes
- **Visible:** job title, session state, next-steps messaging

### HR/User View (console-web, M10-F01)
- JWT: org-scoped, role=user or admin
- **Visible:** assessment counts, session list, completion trends, all scores in reports
- **Not visible:** billing/plan status (stub for now, M12)

### Admin View (console-web, M10-F03)
- JWT: org-scoped, role=admin
- **Visible:** users, competencies, templates, admin tables
- **Not visible:** individual session data (not admin's domain)

### Reports View (console-web, M10-F04)
- JWT: org-scoped, role=user or admin
- **Visible:** all completed reports, verdicts, scores
- **Filtering:** respects org_id in claims; users see only their org's reports

---

## Component Reuse Matrix

```
                    SummaryCard  FilterBar  ChartCard
HR Dashboard              ✓         ✓         ~
Admin Dashboard           ✓         ✓         
Reports Dashboard         ~         ✓         ✓
Candidate Dashboard                           
Analytics (M11)           ~         ✓         ✓
```

- ✓ = Core use
- ~ = Optional/nice-to-have
- Blank = Not used

---

## Testing Strategy

### Unit Tests (components)
- `SummaryCard.test.tsx`: render with/without badge, trend, loading
- `FilterBar.test.tsx`: filter state management, onApply/onReset callbacks
- `ChartCard.test.tsx`: render different chart types, responsive

### Integration Tests (pages)
- HR Dashboard: fetch + filter + navigate to report
- Admin Dashboard: render user/competency/template tables
- Reports Dashboard: filter + pagination + search
- Candidate Dashboard: session data load + no score leakage

### E2E Tests (Playwright, smoke)
- Login as HR user → navigate HR Dashboard → click a session → verify report detail loads
- Login as admin → navigate Admin Dashboard → verify tables render
- Login as candidate → view status page → verify no scores visible
- Login as HR user → navigate Reports Dashboard → search + filter → download PDF

---

## Implementation Order

1. **Phase 1 (this session):** Shared components (SummaryCard, FilterBar, ChartCard) + layout structure
2. **Phase 2:** HR Dashboard (F01) — simplest; data all exists
3. **Phase 3:** Admin Dashboard (F03) — straightforward table views
4. **Phase 4:** Reports Dashboard (F04) — filtering + pagination + charts
5. **Phase 5:** Candidate Dashboard (F02) — most constrained (security-critical)

---

## Key Decisions

1. **Shared components in both apps:** `SummaryCard`, `FilterBar`, `ChartCard` duplicated across console-web and candidate-web. Acceptable duplication (not extracted to package) because candidate-web may diverge (e.g., mobile-only styling).

2. **No new backend routes:** Existing M1–M9 endpoints surface all data; this is a frontend-only composition layer.

3. **Candidate score safety:** Type-level guarantee via TypeScript schema separation (`FullReportResponse` only returned on `require_user`, `SharedReportResponse` strips fields). Enforce at API level (no `require_candidate` returning score fields).

4. **Pagination via URL state:** Reports Dashboard state (filters, page number) in `?filters=...&offset=...` — survives refresh, shareable.

5. **Analytics endpoints (M11):** Designed here but implemented in Phase 5; dashboards pre-wired for lazy integration.

6. **Admin billing/plan:** Stubbed with TODO comment for Phase 6 (M12 depends on billing system).

---

## Success Criteria (Exit)

- [ ] All three shared components render with correct props and styling
- [ ] HR Dashboard loads active/in-progress/awaiting-review/pending counts from API
- [ ] HR Dashboard filters by status, renders Recent Sessions table, quick-link navigation works
- [ ] Admin Dashboard renders User, Competency, Template tables with live data
- [ ] Reports Dashboard renders filterable, paginated list; verdicts + score-band filters work
- [ ] Reports Dashboard shows verdict distribution (pie) + score-band distribution (bar)
- [ ] Candidate Dashboard loads from SessionContext, exposes only job title + status (no scores)
- [ ] All four dashboards visually verified in browser (light + dark mode)
- [ ] TypeScript strict mode: all pages pass type-check
- [ ] Accessibility: WCAG 2.1 AA focus rings on interactive elements
- [ ] Security: no raw scores in candidate views (test data exposure via network tab)

# Console Shell Design — ARAP Phase 0

**Date:** 2026-07-22  
**PRD refs:** §4.2 (RBAC), §11.1 (console UI), §11.2 (monorepo)  
**Task:** TASK-000, session `frontend-console`  
**Scope:** `apps/console-web/` only

---

## 1. Objective

Build the HR/Admin console shell — a navigable, RBAC-gated Next.js 14 app with stub pages for every module and shared UI components that all future list screens will reuse. No live data; all values are placeholders.

Exit criteria:
- Shell navigable across all module stubs
- RBAC-gated routes correctly hide Admin-only sections from User role (nav + middleware)
- Typed API client wired and ready for Phase 1 endpoints

---

## 2. Architecture: Route Groups + Middleware (Approach B)

### Route structure

```
/login                    # public — login form
/(console)/               # authenticated route group
  /                       # dashboard
  /assessments            # M1 — Job Assessments stub
  /candidates             # Candidates/Sessions stub
  /reports                # M10-F04 Reports stub
  /analytics              # M11 Analytics stub
  /admin                  # M10-F03/M12 Admin stub — Admin role only
```

### Auth flow

1. `POST /api/auth/login` → server sets `refresh_token` httpOnly cookie; returns `{ access_token }` in JSON
2. `AuthContext` stores `{ role, accessToken }` in React memory (never persisted to localStorage)
3. `middleware.ts` reads `refresh_token` cookie:
   - Absent → redirect `/login`
   - Role=`user` + path starts `/admin` → redirect `/`
4. `api-client.ts`: on 401 response → call `POST /api/auth/refresh` (cookie auto-sent) → retry once → on second 401 clear context + redirect `/login`

### Token details

- Access token: short-lived JWT, stored in `AuthContext` memory only
- Refresh token: opaque 32-byte secret in httpOnly cookie (set by server)
- Client never verifies JWT signature — payload decoded via base64 split for `role` + `orgId` only

---

## 3. File Structure

```
apps/console-web/src/
├── app/
│   ├── layout.tsx                    # root: providers (AuthProvider) only, no chrome
│   ├── login/page.tsx                # public login form
│   ├── (console)/
│   │   ├── layout.tsx                # console chrome: Sidebar + Topbar
│   │   ├── page.tsx                  # dashboard (SummaryCard grid)
│   │   ├── assessments/page.tsx      # M1 stub
│   │   ├── candidates/page.tsx       # Candidates/Sessions stub
│   │   ├── reports/page.tsx          # Reports stub (M10-F04)
│   │   ├── analytics/page.tsx        # Analytics stub (M11, ChartCard)
│   │   └── admin/page.tsx            # Admin stub (M10-F03/M12)
│   └── globals.css
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx               # role-aware nav; Admin item hidden for user role
│   │   └── Topbar.tsx                # shows role badge + logout button
│   └── ui/
│       ├── SummaryCard.tsx
│       ├── FilterBar.tsx
│       ├── ChartCard.tsx
│       └── ReportCard.tsx
├── context/
│   └── AuthContext.tsx               # AuthProvider + useAuth() hook
├── lib/
│   ├── api-client.ts                 # typed fetch; Bearer injection; 401 refresh+retry
│   └── auth.ts                       # login(), refresh(), logout() API calls
├── middleware.ts                     # cookie check; /admin role gate
└── types/
    └── auth.ts                       # ConsoleUser, TokenClaims interfaces
```

---

## 4. Shared Components

### SummaryCard
```typescript
interface SummaryCardProps {
  label: string;
  value: string | number;
  delta?: string;       // e.g. "+12% vs last week"
}
```
Renders a white card with label (xs, slate-500), value (2xl semibold), optional delta (xs, green/red).

### FilterBar
```typescript
interface FilterDef {
  key: string;
  label: string;
  options: { label: string; value: string }[];
}
interface FilterBarProps {
  search: string;
  onSearch: (v: string) => void;
  filters: FilterDef[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
}
```
Renders a search input + one `<select>` per filter definition. Stateless — parent owns state.

### ChartCard
```typescript
interface ChartCardProps {
  title: string;
  children: React.ReactNode;  // Recharts component goes here
}
```
White card with title bar; `children` fills the chart area. Stub analytics page passes a placeholder `<BarChart>`.

### ReportCard
```typescript
interface ReportCardProps {
  title: string;
  meta: string;         // e.g. "Generated 2026-07-22 · PDF"
  onDownload?: () => void;
}
```
Row card with title, meta text, and optional Download button.

---

## 5. RBAC Nav Visibility

| Nav item        | admin | user |
|-----------------|:-----:|:----:|
| Dashboard       |  ✓    |  ✓   |
| Job Assessments |  ✓    |  ✓   |
| Candidates      |  ✓    |  ✓   |
| Reports         |  ✓    |  ✓   |
| Analytics       |  ✓    |  ✓   |
| Admin           |  ✓    |  ✗   |

Enforcement is dual-layer:
1. Sidebar filters `navItems` by `item.roles.includes(role)` — Admin item never renders for User
2. `middleware.ts` blocks `/admin/*` for role=`user` — direct URL access still redirects

---

## 6. Typed API Client

`api-client.ts` exports one function:

```typescript
async function apiRequest<T>(
  path: string,
  options?: RequestInit & { skipAuth?: boolean }
): Promise<T>
```

- Reads access token from `AuthContext` via a module-level getter (avoids React hook in non-component code)
- Sets `Authorization: Bearer <token>` unless `skipAuth: true`
- On 401: calls `auth.refresh()`, updates context, retries once; on second 401 → calls `logout()`
- Base URL: `process.env.NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`)

---

## 7. Dependencies to Add

| Package | Reason |
|---------|--------|
| `recharts` | ChartCard — BarChart placeholder in analytics stub |

No other new deps. `jose` not needed — JWT payload decoded client-side with `atob()` (no signature verification; server is authoritative).

---

## 8. What Is NOT in This Spec

- Real data fetching (Phase 1+)
- Candidate-web shell (separate task/TASK-001)
- Magic-link / OTP login flows (candidate-only, not used in console)
- Any M1–M12 feature logic
- Responsive breakpoints below tablet (desktop-first; tablet functional means layout doesn't break at md)

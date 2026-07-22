# Console Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the ARAP HR/Admin console shell — navigable stub pages for all 5 modules with RBAC-gated routes, a typed API client, JWT auth/refresh, and shared UI components reused across every list screen.

**Architecture:** Next.js 14 App Router with a `(console)` route group gating all authenticated pages; `middleware.ts` reads a `refresh_token` httpOnly cookie to protect the group and block `/admin` for the `user` role; access token lives in React context (in-memory only). All pages are stubs — no live data.

**Tech Stack:** Next.js 14.2.5, TypeScript 5, Tailwind CSS 3, Recharts, `@arap/shared-types` (`Role`)

## Global Constraints

- Next.js config must remain `next.config.mjs` — `next.config.ts` is unsupported in 14.2.5
- All work is inside `apps/console-web/src/` — do not touch any other app or service
- Base font: Inter, 0.8rem (already set in `globals.css`) — do not change
- Color palette: slate-800 sidebar, white content area, slate-50 page bg (already set)
- API base URL read from `process.env.NEXT_PUBLIC_API_URL` — default `http://localhost:8000`
- `@arap/shared-types` provides `Role = "admin" | "user" | "candidate" | "client"` — import from there, do not redefine
- No test framework is installed — verification is `tsc --noEmit` + `next build` after each task
- Commit format: `[TASK-000] <type>: <what changed>`

---

## File Map

| File | Status | Responsibility |
|------|--------|----------------|
| `src/types/auth.ts` | **Create** | `ConsoleUser`, `TokenClaims` interfaces |
| `src/context/AuthContext.tsx` | **Create** | `AuthProvider`, `useAuth()` hook — role + access token in memory |
| `src/lib/auth.ts` | **Create** | `login()`, `refresh()`, `logout()` — raw API calls |
| `src/lib/api-client.ts` | **Create** | `apiRequest<T>()` — typed fetch, Bearer injection, 401 retry |
| `src/middleware.ts` | **Create** | Cookie presence check; `/admin` role gate |
| `src/app/layout.tsx` | **Modify** | Root layout — providers only, no chrome |
| `src/app/(console)/layout.tsx` | **Create** | Console chrome: Sidebar + Topbar |
| `src/app/(console)/page.tsx` | **Create** | Dashboard (SummaryCard grid, replaces old `app/page.tsx`) |
| `src/app/login/page.tsx` | **Create** | Public login form |
| `src/app/(console)/assessments/page.tsx` | **Create** | M1 stub |
| `src/app/(console)/candidates/page.tsx` | **Create** | Candidates/Sessions stub |
| `src/app/(console)/reports/page.tsx` | **Create** | Reports stub (M10-F04) |
| `src/app/(console)/analytics/page.tsx` | **Create** | Analytics stub (M11, ChartCard) |
| `src/app/(console)/admin/page.tsx` | **Create** | Admin stub (M10-F03/M12) |
| `src/components/layout/Sidebar.tsx` | **Modify** | Role-aware nav; Admin hidden for `user` |
| `src/components/layout/Topbar.tsx` | **Modify** | Role badge + logout button |
| `src/components/ui/SummaryCard.tsx` | **Create** | label + value + optional delta |
| `src/components/ui/FilterBar.tsx` | **Create** | Search input + select filters (stateless) |
| `src/components/ui/ChartCard.tsx` | **Create** | Recharts wrapper card |
| `src/components/ui/ReportCard.tsx` | **Create** | Report row: title + meta + download |

---

## Task 1: Auth Types

**Files:**
- Create: `src/types/auth.ts`

**Interfaces:**
- Produces: `ConsoleUser`, `TokenClaims` — consumed by Tasks 2, 3, 4

- [ ] **Step 1: Create the types file**

```typescript
// src/types/auth.ts
import type { Role } from "@arap/shared-types";

export interface TokenClaims {
  sub: string;       // user ID (UUID)
  role: Role;
  org_id: string;    // org UUID
  exp: number;       // unix timestamp
}

export interface ConsoleUser {
  id: string;
  role: Role;
  orgId: string;
}
```

- [ ] **Step 2: Verify TypeScript**

```
cd apps/console-web
npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 3: Commit**

```
git add apps/console-web/src/types/auth.ts
git commit -m "[TASK-000] feat: add console auth types (ConsoleUser, TokenClaims)"
```

---

## Task 2: AuthContext

**Files:**
- Create: `src/context/AuthContext.tsx`

**Interfaces:**
- Consumes: `ConsoleUser` from `src/types/auth.ts`
- Produces:
  ```typescript
  useAuth(): {
    user: ConsoleUser | null;
    accessToken: string | null;
    setAuth(user: ConsoleUser, accessToken: string): void;
    clearAuth(): void;
  }
  AuthProvider: React.FC<{ children: React.ReactNode }>
  ```

- [ ] **Step 1: Create AuthContext**

```typescript
// src/context/AuthContext.tsx
"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import type { ConsoleUser } from "@/types/auth";

interface AuthState {
  user: ConsoleUser | null;
  accessToken: string | null;
}

interface AuthContextValue extends AuthState {
  setAuth: (user: ConsoleUser, accessToken: string) => void;
  clearAuth: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
  });

  const setAuth = useCallback((user: ConsoleUser, accessToken: string) => {
    setState({ user, accessToken });
  }, []);

  const clearAuth = useCallback(() => {
    setState({ user: null, accessToken: null });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, setAuth, clearAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
```

- [ ] **Step 2: Verify TypeScript**

```
cd apps/console-web
npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 3: Commit**

```
git add apps/console-web/src/context/AuthContext.tsx
git commit -m "[TASK-000] feat: add AuthContext with in-memory token storage"
```

---

## Task 3: Auth Lib + API Client

**Files:**
- Create: `src/lib/auth.ts`
- Create: `src/lib/api-client.ts`

**Interfaces:**
- Consumes: `ConsoleUser`, `TokenClaims` from `src/types/auth.ts`; `clearAuth` + `setAuth` from `AuthContext` (passed in, not imported directly — avoids hook-outside-component)
- Produces:
  ```typescript
  // auth.ts
  login(email: string, password: string): Promise<{ user: ConsoleUser; accessToken: string }>
  refresh(): Promise<{ user: ConsoleUser; accessToken: string }>
  logout(): Promise<void>
  decodeToken(token: string): TokenClaims

  // api-client.ts
  createApiClient(getToken: () => string | null, onUnauth: () => void): {
    request<T>(path: string, options?: RequestInit & { skipAuth?: boolean }): Promise<T>
  }
  ```

- [ ] **Step 1: Create auth.ts**

```typescript
// src/lib/auth.ts
import type { ConsoleUser, TokenClaims } from "@/types/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function decodeToken(token: string): TokenClaims {
  const payload = token.split(".")[1];
  const decoded = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
  return decoded as TokenClaims;
}

function claimsToUser(claims: TokenClaims): ConsoleUser {
  return { id: claims.sub, role: claims.role, orgId: claims.org_id };
}

export async function login(
  email: string,
  password: string
): Promise<{ user: ConsoleUser; accessToken: string }> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Login failed");
  }
  const { access_token } = (await res.json()) as { access_token: string };
  const claims = decodeToken(access_token);
  return { user: claimsToUser(claims), accessToken: access_token };
}

export async function refresh(): Promise<{ user: ConsoleUser; accessToken: string }> {
  const res = await fetch(`${API_BASE}/api/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Refresh failed");
  const { access_token } = (await res.json()) as { access_token: string };
  const claims = decodeToken(access_token);
  return { user: claimsToUser(claims), accessToken: access_token };
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  }).catch(() => undefined);
}
```

- [ ] **Step 2: Create api-client.ts**

```typescript
// src/lib/api-client.ts
import { refresh } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function createApiClient(
  getToken: () => string | null,
  onUnauth: () => void
) {
  async function request<T>(
    path: string,
    options: RequestInit & { skipAuth?: boolean } = {}
  ): Promise<T> {
    const { skipAuth, ...fetchOptions } = options;
    const headers = new Headers(fetchOptions.headers);

    if (!skipAuth) {
      const token = getToken();
      if (token) headers.set("Authorization", `Bearer ${token}`);
    }

    const res = await fetch(`${API_BASE}${path}`, {
      ...fetchOptions,
      headers,
      credentials: "include",
    });

    if (res.status === 401 && !skipAuth) {
      try {
        const { accessToken: newToken } = await refresh();
        headers.set("Authorization", `Bearer ${newToken}`);
        const retry = await fetch(`${API_BASE}${path}`, {
          ...fetchOptions,
          headers,
          credentials: "include",
        });
        if (retry.status === 401) {
          onUnauth();
          throw new Error("Session expired");
        }
        return retry.json() as Promise<T>;
      } catch {
        onUnauth();
        throw new Error("Session expired");
      }
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(
        (err as { detail?: string }).detail ?? `Request failed: ${res.status}`
      );
    }

    return res.json() as Promise<T>;
  }

  return { request };
}
```

- [ ] **Step 3: Verify TypeScript**

```
cd apps/console-web
npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 4: Commit**

```
git add apps/console-web/src/lib/auth.ts apps/console-web/src/lib/api-client.ts
git commit -m "[TASK-000] feat: add auth lib and typed API client with 401 refresh retry"
```

---

## Task 4: Middleware

**Files:**
- Create: `src/middleware.ts` (in `apps/console-web/src/`, NOT project root)

**Interfaces:**
- Consumes: nothing from our code — reads `refresh_token` cookie and `role` from request headers (set by auth context on navigation — note: middleware runs on server, can only read cookies, not in-memory context; role gate is enforced by cookie presence + a `x-user-role` cookie set at login)
- Produces: redirect responses for unauthenticated / unauthorized access

> **Note on role in middleware:** The server sets a `user_role` cookie (plain string, not httpOnly) alongside the `refresh_token` httpOnly cookie at login so middleware can read the role for the `/admin` gate without decoding the JWT. The login response must set both cookies. If `user_role` cookie is absent, treat as `user` (deny admin).

- [ ] **Step 1: Create middleware.ts**

```typescript
// src/middleware.ts
import { NextResponse, type NextRequest } from "next/server";

const PUBLIC_PATHS = ["/login"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  const refreshToken = request.cookies.get("refresh_token");
  if (!refreshToken) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    return NextResponse.redirect(loginUrl);
  }

  if (pathname.startsWith("/admin")) {
    const role = request.cookies.get("user_role")?.value ?? "user";
    if (role !== "admin") {
      const dashUrl = request.nextUrl.clone();
      dashUrl.pathname = "/";
      return NextResponse.redirect(dashUrl);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/).*)"],
};
```

- [ ] **Step 2: Update auth.ts to set user_role cookie on login**

The `user_role` cookie is set by the **server** in the login response. The client does not set it. Update the comment in `src/lib/auth.ts` to note this:

```typescript
// src/lib/auth.ts — add comment above login()
// NOTE: The server sets both `refresh_token` (httpOnly) and `user_role` (plain)
// cookies in the Set-Cookie header of the login response.
// middleware.ts reads `user_role` to gate the /admin route.
export async function login(
  // ... rest unchanged
```

- [ ] **Step 3: Verify TypeScript**

```
cd apps/console-web
npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 4: Commit**

```
git add apps/console-web/src/middleware.ts apps/console-web/src/lib/auth.ts
git commit -m "[TASK-000] feat: add Next.js middleware for auth cookie check and admin role gate"
```

---

## Task 5: Layout Restructure

**Files:**
- Modify: `src/app/layout.tsx` — strip chrome, add AuthProvider
- Create: `src/app/(console)/layout.tsx` — console chrome
- Create: `src/app/(console)/page.tsx` — dashboard (replaces `src/app/page.tsx`)
- Delete: `src/app/page.tsx` (after creating the console version)

**Interfaces:**
- Consumes: `AuthProvider` from `src/context/AuthContext.tsx`
- Produces: authenticated layout shell used by all `(console)` pages

- [ ] **Step 1: Update root layout.tsx (providers only)**

```typescript
// src/app/layout.tsx
import type { Metadata } from "next";
import { AuthProvider } from "@/context/AuthContext";
import "./globals.css";

export const metadata: Metadata = {
  title: "ARAP Console",
  description: "AI Recruitment Assessment Platform — HR/Admin Console",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-900 antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Create (console)/layout.tsx**

```typescript
// src/app/(console)/layout.tsx
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";

export default function ConsoleLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0">
        <Topbar />
        <main className="flex-1 p-6 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Move existing dashboard to (console)/page.tsx**

Create `src/app/(console)/page.tsx`:

```typescript
// src/app/(console)/page.tsx
import { SummaryCard } from "@/components/ui/SummaryCard";

const stats = [
  { label: "Active Assessments", value: "—" },
  { label: "Candidates", value: "—" },
  { label: "Reports Generated", value: "—" },
  { label: "Avg. Verdict Time", value: "—" },
];

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-800">Dashboard</h1>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <SummaryCard key={stat.label} label={stat.label} value={stat.value} />
        ))}
      </div>
      <p className="text-xs text-slate-400">
        Console shell — features coming in Phase 1.
      </p>
    </div>
  );
}
```

- [ ] **Step 4: Delete the old app/page.tsx**

```
rm apps/console-web/src/app/page.tsx
```

- [ ] **Step 5: Move Sidebar and Topbar to layout/ subfolder**

```
mkdir -p apps/console-web/src/components/layout
mv apps/console-web/src/components/Sidebar.tsx apps/console-web/src/components/layout/Sidebar.tsx
mv apps/console-web/src/components/Topbar.tsx apps/console-web/src/components/layout/Topbar.tsx
```

> The layout files will be rewritten in Task 7 — the move just clears the path.

- [ ] **Step 6: Verify TypeScript**

```
cd apps/console-web
npx tsc --noEmit
```
Expected: errors about SummaryCard not existing yet — that is acceptable at this step; resolve after Task 6

- [ ] **Step 7: Commit**

```
git add apps/console-web/src/app/layout.tsx
git add "apps/console-web/src/app/(console)/layout.tsx"
git add "apps/console-web/src/app/(console)/page.tsx"
git rm apps/console-web/src/app/page.tsx
git add apps/console-web/src/components/layout/
git rm apps/console-web/src/components/Sidebar.tsx apps/console-web/src/components/Topbar.tsx
git commit -m "[TASK-000] refactor: restructure to (console) route group, move layout components"
```

---

## Task 6: Shared UI Components

**Files:**
- Create: `src/components/ui/SummaryCard.tsx`
- Create: `src/components/ui/FilterBar.tsx`
- Create: `src/components/ui/ReportCard.tsx`

**Interfaces:**
- Produces:
  ```typescript
  SummaryCard({ label, value, delta? }: SummaryCardProps): JSX.Element
  FilterBar({ search, onSearch, filters, values, onChange }: FilterBarProps): JSX.Element
  ReportCard({ title, meta, onDownload? }: ReportCardProps): JSX.Element
  ```

- [ ] **Step 1: Create SummaryCard.tsx**

```typescript
// src/components/ui/SummaryCard.tsx
interface SummaryCardProps {
  label: string;
  value: string | number;
  delta?: string;
}

export function SummaryCard({ label, value, delta }: SummaryCardProps) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-1">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-2xl font-semibold text-slate-800">{value}</p>
      {delta && (
        <p
          className={`text-xs ${
            delta.startsWith("-") ? "text-red-500" : "text-emerald-600"
          }`}
        >
          {delta}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create FilterBar.tsx**

```typescript
// src/components/ui/FilterBar.tsx
export interface FilterDef {
  key: string;
  label: string;
  options: { label: string; value: string }[];
}

interface FilterBarProps {
  search: string;
  onSearch: (value: string) => void;
  filters: FilterDef[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
}

export function FilterBar({
  search,
  onSearch,
  filters,
  values,
  onChange,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <input
        type="search"
        placeholder="Search…"
        value={search}
        onChange={(e) => onSearch(e.target.value)}
        className="h-8 rounded border border-slate-200 px-3 text-sm
                   text-slate-700 placeholder:text-slate-400
                   focus:outline-none focus:ring-1 focus:ring-slate-400
                   w-48"
      />
      {filters.map((f) => (
        <select
          key={f.key}
          value={values[f.key] ?? ""}
          onChange={(e) => onChange(f.key, e.target.value)}
          className="h-8 rounded border border-slate-200 px-2 text-sm
                     text-slate-700 focus:outline-none focus:ring-1
                     focus:ring-slate-400"
        >
          <option value="">{f.label}</option>
          {f.options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Create ReportCard.tsx**

```typescript
// src/components/ui/ReportCard.tsx
interface ReportCardProps {
  title: string;
  meta: string;
  onDownload?: () => void;
}

export function ReportCard({ title, meta, onDownload }: ReportCardProps) {
  return (
    <div className="flex items-center justify-between bg-white rounded-lg
                    border border-slate-200 px-4 py-3">
      <div className="space-y-0.5">
        <p className="text-sm font-medium text-slate-800">{title}</p>
        <p className="text-xs text-slate-500">{meta}</p>
      </div>
      {onDownload && (
        <button
          onClick={onDownload}
          className="text-xs text-slate-600 hover:text-slate-900
                     border border-slate-200 rounded px-2 py-1
                     hover:border-slate-400 transition-colors"
        >
          Download
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Verify TypeScript**

```
cd apps/console-web
npx tsc --noEmit
```
Expected: no errors (SummaryCard is now defined; dashboard page resolves)

- [ ] **Step 5: Commit**

```
git add apps/console-web/src/components/ui/
git commit -m "[TASK-000] feat: add SummaryCard, FilterBar, ReportCard shared components"
```

---

## Task 7: Recharts + ChartCard

**Files:**
- Modify: `apps/console-web/package.json` (add recharts)
- Create: `src/components/ui/ChartCard.tsx`

**Interfaces:**
- Produces:
  ```typescript
  ChartCard({ title, children }: { title: string; children: ReactNode }): JSX.Element
  ```

- [ ] **Step 1: Install recharts**

```
cd apps/console-web
pnpm add recharts
```
Expected: recharts appears in `package.json` dependencies

- [ ] **Step 2: Create ChartCard.tsx**

```typescript
// src/components/ui/ChartCard.tsx
import type { ReactNode } from "react";

interface ChartCardProps {
  title: string;
  children: ReactNode;
}

export function ChartCard({ title, children }: ChartCardProps) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
      <p className="text-sm font-medium text-slate-700">{title}</p>
      <div className="w-full">{children}</div>
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript**

```
cd apps/console-web
npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 4: Commit**

```
git add apps/console-web/package.json apps/console-web/src/components/ui/ChartCard.tsx
git commit -m "[TASK-000] feat: add recharts dependency and ChartCard component"
```

---

## Task 8: Role-Aware Sidebar + Topbar

**Files:**
- Modify: `src/components/layout/Sidebar.tsx` (rewrite — was moved in Task 5)
- Modify: `src/components/layout/Topbar.tsx` (rewrite — was moved in Task 5)

**Interfaces:**
- Consumes: `useAuth()` from `src/context/AuthContext.tsx`
- Produces: Sidebar that hides Admin nav item for `user` role; Topbar with role badge and logout button

- [ ] **Step 1: Rewrite Sidebar.tsx**

```typescript
// src/components/layout/Sidebar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import type { Role } from "@arap/shared-types";

interface NavItem {
  label: string;
  href: string;
  roles: Role[];
}

const navItems: NavItem[] = [
  { label: "Dashboard", href: "/", roles: ["admin", "user"] },
  { label: "Job Assessments", href: "/assessments", roles: ["admin", "user"] },
  { label: "Candidates", href: "/candidates", roles: ["admin", "user"] },
  { label: "Reports", href: "/reports", roles: ["admin", "user"] },
  { label: "Analytics", href: "/analytics", roles: ["admin", "user"] },
  { label: "Admin", href: "/admin", roles: ["admin"] },
];

export function Sidebar() {
  const { user } = useAuth();
  const pathname = usePathname();
  const role = user?.role ?? "user";

  const visible = navItems.filter((item) => item.roles.includes(role));

  return (
    <aside className="flex flex-col w-56 min-h-screen bg-slate-800
                      text-slate-300 shrink-0">
      <div className="px-4 py-5 border-b border-slate-700">
        <span className="text-white font-semibold text-sm tracking-wide">
          ARAP Console
        </span>
      </div>
      <nav className="flex-1 px-2 py-4 space-y-1">
        {visible.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center px-3 py-2 rounded-md text-sm
                         transition-colors ${
                           active
                             ? "bg-slate-700 text-white"
                             : "text-slate-300 hover:bg-slate-700 hover:text-white"
                         }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 2: Rewrite Topbar.tsx**

```typescript
// src/components/layout/Topbar.tsx
"use client";

import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { logout } from "@/lib/auth";

const pageTitle: Record<string, string> = {
  "/": "Dashboard",
  "/assessments": "Job Assessments",
  "/candidates": "Candidates",
  "/reports": "Reports",
  "/analytics": "Analytics",
  "/admin": "Admin",
};

export function Topbar() {
  const { user, clearAuth } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const title = pageTitle[pathname] ?? "Console";

  async function handleLogout() {
    await logout();
    clearAuth();
    router.push("/login");
  }

  return (
    <header className="h-12 flex items-center justify-between px-6
                       bg-white border-b border-slate-200 shrink-0">
      <span className="text-sm font-medium text-slate-600">{title}</span>
      <div className="flex items-center gap-3">
        {user && (
          <span className="text-xs text-slate-400 capitalize">{user.role}</span>
        )}
        <button
          onClick={handleLogout}
          className="text-xs text-slate-500 hover:text-slate-800
                     transition-colors"
        >
          Log out
        </button>
      </div>
    </header>
  );
}
```

- [ ] **Step 3: Verify TypeScript**

```
cd apps/console-web
npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 4: Commit**

```
git add apps/console-web/src/components/layout/Sidebar.tsx
git add apps/console-web/src/components/layout/Topbar.tsx
git commit -m "[TASK-000] feat: role-aware Sidebar (hides Admin for user role) and Topbar with logout"
```

---

## Task 9: Login Page

**Files:**
- Create: `src/app/login/page.tsx`

**Interfaces:**
- Consumes: `login()` from `src/lib/auth.ts`; `setAuth` from `useAuth()`
- Produces: `/login` public page — form → calls login() → sets context → redirects to `/`

- [ ] **Step 1: Create login page**

```typescript
// src/app/login/page.tsx
"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/auth";
import { useAuth } from "@/context/AuthContext";

export default function LoginPage() {
  const { setAuth } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { user, accessToken } = await login(email, password);
      setAuth(user, accessToken);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="bg-white rounded-lg border border-slate-200 p-8 w-80 space-y-5">
        <div className="space-y-1">
          <h1 className="text-base font-semibold text-slate-800">ARAP Console</h1>
          <p className="text-xs text-slate-500">Sign in to continue</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1">
            <label className="text-xs text-slate-600">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full h-8 rounded border border-slate-200 px-3
                         text-sm text-slate-800 focus:outline-none
                         focus:ring-1 focus:ring-slate-400"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-slate-600">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full h-8 rounded border border-slate-200 px-3
                         text-sm text-slate-800 focus:outline-none
                         focus:ring-1 focus:ring-slate-400"
            />
          </div>
          {error && <p className="text-xs text-red-500">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full h-8 rounded bg-slate-800 text-white text-sm
                       hover:bg-slate-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```
cd apps/console-web
npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 3: Commit**

```
git add "apps/console-web/src/app/login/page.tsx"
git commit -m "[TASK-000] feat: add login page with email/password form"
```

---

## Task 10: Module Stub Pages

**Files:**
- Create: `src/app/(console)/assessments/page.tsx`
- Create: `src/app/(console)/candidates/page.tsx`
- Create: `src/app/(console)/reports/page.tsx`
- Create: `src/app/(console)/analytics/page.tsx`
- Create: `src/app/(console)/admin/page.tsx`

**Interfaces:**
- Consumes: `SummaryCard`, `FilterBar`, `ChartCard`, `ReportCard` from `src/components/ui/`

- [ ] **Step 1: Create assessments/page.tsx**

```typescript
// src/app/(console)/assessments/page.tsx
"use client";

import { useState } from "react";
import { SummaryCard } from "@/components/ui/SummaryCard";
import { FilterBar, type FilterDef } from "@/components/ui/FilterBar";

const filters: FilterDef[] = [
  {
    key: "status",
    label: "Status",
    options: [
      { label: "Active", value: "active" },
      { label: "Draft", value: "draft" },
      { label: "Closed", value: "closed" },
    ],
  },
];

export default function AssessmentsPage() {
  const [search, setSearch] = useState("");
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-800">Job Assessments</h1>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <SummaryCard label="Total Assessments" value="—" />
        <SummaryCard label="Active" value="—" />
        <SummaryCard label="Avg. Completion Rate" value="—" />
      </div>
      <FilterBar
        search={search}
        onSearch={setSearch}
        filters={filters}
        values={filterValues}
        onChange={(k, v) => setFilterValues((prev) => ({ ...prev, [k]: v }))}
      />
      <p className="text-xs text-slate-400">Assessment list — Phase 1.</p>
    </div>
  );
}
```

- [ ] **Step 2: Create candidates/page.tsx**

```typescript
// src/app/(console)/candidates/page.tsx
"use client";

import { useState } from "react";
import { SummaryCard } from "@/components/ui/SummaryCard";
import { FilterBar, type FilterDef } from "@/components/ui/FilterBar";

const filters: FilterDef[] = [
  {
    key: "status",
    label: "Session Status",
    options: [
      { label: "In Progress", value: "in_progress" },
      { label: "Completed", value: "completed" },
      { label: "Pending", value: "pending" },
    ],
  },
];

export default function CandidatesPage() {
  const [search, setSearch] = useState("");
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-800">Candidates & Sessions</h1>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <SummaryCard label="Total Candidates" value="—" />
        <SummaryCard label="Active Sessions" value="—" />
        <SummaryCard label="Completed Today" value="—" />
      </div>
      <FilterBar
        search={search}
        onSearch={setSearch}
        filters={filters}
        values={filterValues}
        onChange={(k, v) => setFilterValues((prev) => ({ ...prev, [k]: v }))}
      />
      <p className="text-xs text-slate-400">Candidate list — Phase 1.</p>
    </div>
  );
}
```

- [ ] **Step 3: Create reports/page.tsx**

```typescript
// src/app/(console)/reports/page.tsx
"use client";

import { useState } from "react";
import { FilterBar, type FilterDef } from "@/components/ui/FilterBar";
import { ReportCard } from "@/components/ui/ReportCard";

const filters: FilterDef[] = [
  {
    key: "type",
    label: "Report Type",
    options: [
      { label: "Assessment", value: "assessment" },
      { label: "Candidate", value: "candidate" },
    ],
  },
];

const placeholderReports = [
  { title: "Weekly Assessment Summary", meta: "Generated — · PDF" },
  { title: "Candidate Pipeline Report", meta: "Generated — · PDF" },
  { title: "Score Distribution Analysis", meta: "Generated — · PDF" },
];

export default function ReportsPage() {
  const [search, setSearch] = useState("");
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-800">Reports</h1>
      <FilterBar
        search={search}
        onSearch={setSearch}
        filters={filters}
        values={filterValues}
        onChange={(k, v) => setFilterValues((prev) => ({ ...prev, [k]: v }))}
      />
      <div className="space-y-2">
        {placeholderReports.map((r) => (
          <ReportCard key={r.title} title={r.title} meta={r.meta} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create analytics/page.tsx**

```typescript
// src/app/(console)/analytics/page.tsx
"use client";

import { SummaryCard } from "@/components/ui/SummaryCard";
import { ChartCard } from "@/components/ui/ChartCard";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const placeholderData = [
  { name: "Mon", count: 0 },
  { name: "Tue", count: 0 },
  { name: "Wed", count: 0 },
  { name: "Thu", count: 0 },
  { name: "Fri", count: 0 },
];

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-800">Analytics</h1>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <SummaryCard label="Sessions This Week" value="—" />
        <SummaryCard label="Pass Rate" value="—" />
        <SummaryCard label="Avg. Score" value="—" />
      </div>
      <ChartCard title="Sessions by Day (placeholder)">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={placeholderData}>
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="count" fill="#475569" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  );
}
```

- [ ] **Step 5: Create admin/page.tsx**

```typescript
// src/app/(console)/admin/page.tsx
import { SummaryCard } from "@/components/ui/SummaryCard";

export default function AdminPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-800">Admin</h1>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <SummaryCard label="Organisations" value="—" />
        <SummaryCard label="Total Users" value="—" />
        <SummaryCard label="Active Orgs" value="—" />
      </div>
      <p className="text-xs text-slate-400">
        Organisation & user management — Phase 1.
      </p>
    </div>
  );
}
```

- [ ] **Step 6: Verify TypeScript**

```
cd apps/console-web
npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 7: Commit**

```
git add "apps/console-web/src/app/(console)/assessments/"
git add "apps/console-web/src/app/(console)/candidates/"
git add "apps/console-web/src/app/(console)/reports/"
git add "apps/console-web/src/app/(console)/analytics/"
git add "apps/console-web/src/app/(console)/admin/"
git commit -m "[TASK-000] feat: add module stub pages (assessments, candidates, reports, analytics, admin)"
```

---

## Task 11: Final Build Verification

**Files:** none new — verification only

- [ ] **Step 1: Full TypeScript check**

```
cd apps/console-web
npx tsc --noEmit
```
Expected: 0 errors, 0 warnings

- [ ] **Step 2: Production build**

```
cd apps/console-web
pnpm build
```
Expected: build completes with no errors; route table shows:
- `/login` (static)
- `/` — `(console)` (dynamic)
- `/assessments`, `/candidates`, `/reports`, `/analytics`, `/admin` — all `(console)`

- [ ] **Step 3: Manual RBAC smoke test**

Start dev server: `pnpm dev`

Verify these manually:
1. Navigate to `http://localhost:3002` without a cookie → redirected to `/login` ✓
2. Navigate to `http://localhost:3002/admin` without a cookie → redirected to `/login` ✓
3. Login form renders at `/login` with email + password fields ✓
4. Sidebar shows 6 items for admin role, 5 items for user role (Admin hidden) ✓
5. Topbar shows role badge and "Log out" button ✓
6. All module stub pages render with their SummaryCard grids ✓
7. Analytics page renders placeholder BarChart ✓

- [ ] **Step 4: Update TASK-000 exit criteria**

In `tasks/TASK-000-phase0-foundation.md`, mark the console shell exit criterion:
```
- [x] Both app shells boot, authenticate, and route-guard by role
```

- [ ] **Step 5: Final commit**

```
git add tasks/TASK-000-phase0-foundation.md
git commit -m "[TASK-000] chore: mark console-web shell exit criterion complete"
```

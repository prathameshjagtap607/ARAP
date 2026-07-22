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

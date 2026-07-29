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
  { label: "Dashboard", href: "/", roles: ["admin", "user", "super_admin"] },
  { label: "Job Assessments", href: "/assessments", roles: ["admin", "user", "super_admin"] },
  { label: "Candidates", href: "/candidates", roles: ["admin", "user", "super_admin"] },
  { label: "Reports", href: "/reports", roles: ["admin", "user", "super_admin"] },
  { label: "Analytics", href: "/analytics", roles: ["admin", "user", "super_admin"] },
  { label: "Admin", href: "/dashboard/admin", roles: ["admin"] },
  { label: "Admin", href: "/admin", roles: ["super_admin"] },
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

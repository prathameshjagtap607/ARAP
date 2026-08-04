'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';

// "HR Dashboard" and "Reports" tabs were removed — the sidebar's Dashboard
// and Reports links already redirect straight into these pages, so the tabs
// only duplicated existing navigation. "Admin" stays since /dashboard/admin
// is a distinct page from the sidebar's /admin (not yet consolidated).
const tabs = [
  { label: 'Admin', href: '/dashboard/admin', adminOnly: true },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';
  const visibleTabs = tabs.filter((tab) => !tab.adminOnly || isAdmin);

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Tabs Navigation */}
        {visibleTabs.length > 0 && (
          <div className="border-b border-slate-200 mb-8">
            <nav className="flex gap-8" aria-label="Dashboard navigation">
              {visibleTabs.map((tab) => {
                const isActive = pathname === tab.href;
                return (
                  <Link
                    key={tab.href}
                    href={tab.href}
                    className={`pb-4 text-sm font-medium transition-colors ${
                      isActive
                        ? 'border-b-2 border-blue-600 text-slate-900'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    {tab.label}
                  </Link>
                );
              })}
            </nav>
          </div>
        )}

        {/* Page Content */}
        <div className="space-y-6">
          {children}
        </div>
      </div>
    </div>
  );
}

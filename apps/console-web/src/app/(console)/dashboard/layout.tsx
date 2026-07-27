'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';

const tabs = [
  { label: 'HR Dashboard', href: '/dashboard' },
  { label: 'Admin', href: '/dashboard/admin' },
  { label: 'Reports', href: '/dashboard/reports' },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Tabs Navigation */}
        <div className="border-b border-slate-200 mb-8">
          <nav className="flex gap-8" aria-label="Dashboard navigation">
            {tabs.map((tab) => {
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

        {/* Page Content */}
        <div className="space-y-6">
          {children}
        </div>
      </div>
    </div>
  );
}

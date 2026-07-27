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

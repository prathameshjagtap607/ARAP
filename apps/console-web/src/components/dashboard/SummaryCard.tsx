import React from "react";
import { SummaryCardProps } from "@/lib/types/dashboard";

const badgeColorMap = {
  amber: "bg-amber-100 text-amber-900",
  green: "bg-green-100 text-green-900",
  red: "bg-red-100 text-red-900",
  blue: "bg-blue-100 text-blue-900",
};

const trendColorMap = {
  up: "text-green-600",
  down: "text-red-600",
  flat: "text-slate-600",
};

const trendIconMap = {
  up: "↑",
  down: "↓",
  flat: "→",
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
  const Container = onClick ? "button" : "div";
  const containerProps = onClick
    ? {
        onClick,
        type: "button" as const,
        className:
          "w-full text-left rounded-lg border border-slate-200 bg-white p-6 hover:border-slate-300 cursor-pointer transition-colors",
      }
    : {
        className: "rounded-lg border border-slate-200 bg-white p-6",
      };

  if (loading) {
    return (
      <div
        className="rounded-lg border border-slate-200 bg-white p-6 animate-pulse"
        data-testid="loading-skeleton"
      >
        <div className="space-y-2">
          <div className="h-4 bg-slate-200 rounded w-32"></div>
          <div className="h-10 bg-slate-200 rounded w-20"></div>
          <div className="h-4 bg-slate-200 rounded w-24"></div>
        </div>
      </div>
    );
  }

  return (
    <Container {...containerProps}>
      <div className="relative">
        {badge && (
          <div
            className={`absolute top-0 right-0 inline-block px-2 py-1 rounded text-xs font-semibold ${badgeColorMap[badge.color]}`}
          >
            {badge.label}
          </div>
        )}

        <div className="space-y-2">
          <div className="text-sm font-medium text-slate-600">{title}</div>

          <div className="flex items-baseline gap-2">
            <div className="flex items-center gap-1">
              {icon && <span className="text-lg">{icon}</span>}
              <span className="text-3xl font-bold text-slate-900">
                {value}
              </span>
            </div>
          </div>

          {trend && (
            <div className={`text-sm font-medium ${trendColorMap[trend.direction]}`}>
              {trend.value >= 0 ? "+" : ""}
              {trend.value} {trendIconMap[trend.direction]}
            </div>
          )}
        </div>
      </div>
    </Container>
  );
}

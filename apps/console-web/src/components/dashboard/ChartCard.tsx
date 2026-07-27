import React from "react";
import {
  BarChart,
  LineChart,
  PieChart,
  ComposedChart,
  Bar,
  Line,
  Pie,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { ChartCardProps } from "@/lib/types/dashboard";

const COLORS = [
  "#3b82f6",
  "#ef4444",
  "#10b981",
  "#f59e0b",
  "#8b5cf6",
  "#ec4899",
];

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
      <div
        className="rounded-lg border border-slate-200 bg-white p-6 animate-pulse"
        data-testid="chart-loading-skeleton"
      >
        <div className="space-y-4">
          <div className="h-6 bg-slate-200 rounded w-48"></div>
          <div className="h-64 bg-slate-100 rounded"></div>
        </div>
      </div>
    );
  }

  const renderChart = () => {
    const containerProps = {
      width: "100%",
      height,
      data,
    };

    switch (chartType) {
      case "bar":
        return (
          <ResponsiveContainer width="100%" height={height} data-testid="bar-chart">
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={xKey} />
              <YAxis />
              <Tooltip />
              <Legend />
              {series && series.length > 0 ? (
                series.map((s, index) => (
                  <Bar
                    key={s.key}
                    dataKey={s.key}
                    fill={s.fill || COLORS[index % COLORS.length]}
                  />
                ))
              ) : yKey ? (
                <Bar dataKey={yKey} fill={COLORS[0]} />
              ) : null}
            </BarChart>
          </ResponsiveContainer>
        );

      case "line":
        return (
          <ResponsiveContainer width="100%" height={height} data-testid="line-chart">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={xKey} />
              <YAxis />
              <Tooltip />
              <Legend />
              {series && series.length > 0 ? (
                series.map((s, index) => (
                  <Line
                    key={s.key}
                    type="monotone"
                    dataKey={s.key}
                    stroke={s.fill || COLORS[index % COLORS.length]}
                  />
                ))
              ) : yKey ? (
                <Line type="monotone" dataKey={yKey} stroke={COLORS[0]} />
              ) : null}
            </LineChart>
          </ResponsiveContainer>
        );

      case "pie":
        return (
          <ResponsiveContainer width="100%" height={height} data-testid="pie-chart">
            <PieChart data={data}>
              <Pie
                dataKey={yKey || "value"}
                nameKey={xKey}
                cx="50%"
                cy="50%"
                label
              >
                {data.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={COLORS[index % COLORS.length]}
                  />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        );

      case "composed":
        return (
          <ResponsiveContainer width="100%" height={height} data-testid="composed-chart">
            <ComposedChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey={xKey} />
              <YAxis />
              <Tooltip />
              <Legend />
              {series && series.length > 0 ? (
                series.map((s, index) => {
                  const colorToUse = s.fill || COLORS[index % COLORS.length];
                  if (index === 0) {
                    return (
                      <Bar key={s.key} dataKey={s.key} fill={colorToUse} />
                    );
                  }
                  return (
                    <Line
                      key={s.key}
                      type="monotone"
                      dataKey={s.key}
                      stroke={colorToUse}
                    />
                  );
                })
              ) : yKey ? (
                <Bar dataKey={yKey} fill={COLORS[0]} />
              ) : null}
            </ComposedChart>
          </ResponsiveContainer>
        );

      default:
        return null;
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6">
      <h3 className="text-lg font-semibold text-slate-900 mb-4">{title}</h3>
      {renderChart()}
    </div>
  );
}

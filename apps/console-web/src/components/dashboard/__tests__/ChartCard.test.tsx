import React from "react";
import { render, screen } from "@testing-library/react";
import ChartCard from "../ChartCard";

describe("ChartCard", () => {
  const mockData = [
    { name: "Jan", value: 100, amount: 50 },
    { name: "Feb", value: 200, amount: 75 },
    { name: "Mar", value: 150, amount: 60 },
  ];

  test("renders title", () => {
    render(
      <ChartCard
        title="Sales Chart"
        data={mockData}
        chartType="bar"
        xKey="name"
        yKey="value"
      />
    );

    expect(screen.getByText("Sales Chart")).toBeInTheDocument();
  });

  test("renders bar chart when chartType is 'bar'", () => {
    render(
      <ChartCard
        title="Bar Chart"
        data={mockData}
        chartType="bar"
        xKey="name"
        yKey="value"
      />
    );

    const chart = screen.getByTestId("bar-chart");
    expect(chart).toBeInTheDocument();
  });

  test("renders line chart when chartType is 'line'", () => {
    render(
      <ChartCard
        title="Line Chart"
        data={mockData}
        chartType="line"
        xKey="name"
        yKey="value"
      />
    );

    const chart = screen.getByTestId("line-chart");
    expect(chart).toBeInTheDocument();
  });

  test("renders pie chart when chartType is 'pie'", () => {
    render(
      <ChartCard
        title="Pie Chart"
        data={mockData}
        chartType="pie"
        xKey="name"
        yKey="value"
      />
    );

    const chart = screen.getByTestId("pie-chart");
    expect(chart).toBeInTheDocument();
  });

  test("renders composed chart when chartType is 'composed'", () => {
    render(
      <ChartCard
        title="Composed Chart"
        data={mockData}
        chartType="composed"
        xKey="name"
        yKey="value"
      />
    );

    const chart = screen.getByTestId("composed-chart");
    expect(chart).toBeInTheDocument();
  });

  test("renders loading skeleton when loading is true", () => {
    render(
      <ChartCard
        title="Loading Chart"
        data={mockData}
        chartType="bar"
        loading={true}
      />
    );

    const skeleton = screen.getByTestId("chart-loading-skeleton");
    expect(skeleton).toBeInTheDocument();
    expect(skeleton).toHaveClass("animate-pulse");
  });

  test("applies correct card styling", () => {
    render(
      <ChartCard
        title="Styled Chart"
        data={mockData}
        chartType="bar"
        xKey="name"
        yKey="value"
      />
    );

    const card = screen.getByText("Styled Chart").closest("div");
    expect(card).toHaveClass(
      "rounded-lg",
      "border",
      "border-slate-200",
      "bg-white",
      "p-6"
    );
  });

  test("renders chart with custom height", () => {
    const { container } = render(
      <ChartCard
        title="Custom Height Chart"
        data={mockData}
        chartType="bar"
        xKey="name"
        yKey="value"
        height={500}
      />
    );

    // The ResponsiveContainer is rendered with the custom height
    const chart = screen.getByTestId("bar-chart");
    expect(chart).toBeInTheDocument();
  });

  test("renders chart with multiple series", () => {
    render(
      <ChartCard
        title="Multi-series Chart"
        data={mockData}
        chartType="bar"
        xKey="name"
        series={[
          { key: "value", fill: "#3b82f6" },
          { key: "amount", fill: "#ef4444" },
        ]}
      />
    );

    const chart = screen.getByTestId("bar-chart");
    expect(chart).toBeInTheDocument();
  });
});

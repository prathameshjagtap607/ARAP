import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import SummaryCard from "../SummaryCard";

describe("SummaryCard", () => {
  test("renders title and value", () => {
    render(<SummaryCard title="Active Assessments" value="12" />);

    expect(screen.getByText("Active Assessments")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  test("renders badge when provided", () => {
    render(
      <SummaryCard
        title="Pending Decisions"
        value="5"
        badge={{ label: "High Priority", color: "red" }}
      />
    );

    const badge = screen.getByText("High Priority");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass("bg-red-100", "text-red-900");
  });

  test("renders loading skeleton when loading is true", () => {
    render(<SummaryCard title="Loading Card" value="0" loading={true} />);

    const skeleton = screen.getByTestId("loading-skeleton");
    expect(skeleton).toBeInTheDocument();
    expect(skeleton).toHaveClass("animate-pulse");
  });

  test("renders trend indicator when provided", () => {
    render(
      <SummaryCard
        title="Completion Rate"
        value="87%"
        trend={{ value: 5, direction: "up" }}
      />
    );

    expect(screen.getByText(/\+5 ↑/)).toBeInTheDocument();
  });

  test("calls onClick handler when clicked", () => {
    const handleClick = jest.fn();
    render(
      <SummaryCard
        title="Clickable Card"
        value="42"
        onClick={handleClick}
      />
    );

    const button = screen.getByRole("button");
    fireEvent.click(button);

    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});

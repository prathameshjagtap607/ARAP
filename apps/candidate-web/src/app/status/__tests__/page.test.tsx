import { render, screen } from "@testing-library/react";
import StatusPage from "../page";
import type { SessionData } from "@/lib/types";

// Mock SessionContext to provide session data
jest.mock("@/context/SessionContext", () => ({
  useSession: () => ({
    state: {
      session: {
        id: "test-session-123",
        job_title: "Senior Software Engineer",
        status: "completed" as const,
        seconds_remaining: null,
        time_budget_seconds: 2700,
        duration_minutes: 45,
        questions: [
          {
            id: "q1",
            sequence_no: 1,
            question: { text: "What is your name?" },
            category: "personal",
            target_competencies: [],
            difficulty: "easy",
            answer_format: "short_text" as const,
            options: null,
            answer_text: "John Doe",
            answered_at: "2026-07-26T10:00:00Z",
          },
          {
            id: "q2",
            sequence_no: 2,
            question: { text: "Describe your experience" },
            category: "experience",
            target_competencies: [],
            difficulty: "medium",
            answer_format: "long_text" as const,
            options: null,
            answer_text: null,
            answered_at: null,
          },
        ],
      } as SessionData,
      jwt: "test-jwt",
      answers: {},
      currentIndex: 0,
      submitting: false,
    },
    dispatch: jest.fn(),
  }),
}));

describe("Candidate Status Page", () => {
  it("renders the page heading", () => {
    render(<StatusPage />);
    expect(
      screen.getByText("Your Assessment Status")
    ).toBeInTheDocument();
  });

  it("renders job title from session", () => {
    render(<StatusPage />);
    expect(
      screen.getByText("Senior Software Engineer")
    ).toBeInTheDocument();
  });

  it("renders duration and question count", () => {
    render(<StatusPage />);
    expect(screen.getByText("45 minutes")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("renders status badge for completed status", () => {
    render(<StatusPage />);
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("displays appropriate message for completed status", () => {
    render(<StatusPage />);
    expect(
      screen.getByText(
        /Your assessment has been submitted successfully/
      )
    ).toBeInTheDocument();
  });

  it("displays What's Next section content", () => {
    render(<StatusPage />);
    expect(screen.getByText("What's Next")).toBeInTheDocument();
    expect(
      screen.getByText(/Your responses have been received/)
    ).toBeInTheDocument();
  });

  it("displays review timeline", () => {
    render(<StatusPage />);
    expect(screen.getByText(/5–7/)).toBeInTheDocument();
  });

  it("SECURITY: does NOT render any raw scores or confidence metrics", () => {
    const { container } = render(<StatusPage />);
    const text = container.textContent || "";

    // These patterns should NOT appear in the document
    expect(text).not.toMatch(/\b\d\.\d{2}\b/); // Score format like 4.62
    expect(text.toLowerCase()).not.toContain("confidence");
    expect(text.toLowerCase()).not.toContain("overall score");
    expect(text.toLowerCase()).not.toContain("competency score");
    expect(text.toLowerCase()).not.toContain("raw score");
    expect(text.toLowerCase()).not.toContain("ai score");
  });

  it("SECURITY: does NOT render competency evaluation data", () => {
    const { container } = render(<StatusPage />);
    const text = container.textContent || "";

    expect(text.toLowerCase()).not.toContain("competency");
    expect(text.toLowerCase()).not.toContain("evaluation");
    expect(text.toLowerCase()).not.toContain("assessed");
  });

  it("SECURITY: does NOT render behavioral data", () => {
    const { container } = render(<StatusPage />);
    const text = container.textContent || "";

    expect(text.toLowerCase()).not.toContain("behavior");
    expect(text.toLowerCase()).not.toContain("personality");
    expect(text.toLowerCase()).not.toContain("traits");
  });

  it("SECURITY: does NOT render salary information", () => {
    const { container } = render(<StatusPage />);
    const text = container.textContent || "";

    expect(text.toLowerCase()).not.toContain("salary");
    expect(text.toLowerCase()).not.toContain("compensation");
    expect(text.toLowerCase()).not.toContain("budget");
  });

  it("SECURITY: does NOT render hiring recommendation", () => {
    const { container } = render(<StatusPage />);
    const text = container.textContent || "";

    expect(text.toLowerCase()).not.toContain("hire");
    expect(text.toLowerCase()).not.toContain("reject");
    expect(text.toLowerCase()).not.toContain("recommendation");
    expect(text.toLowerCase()).not.toContain("verdict");
  });

  it("SECURITY: does NOT render internal flags or labels", () => {
    const { container } = render(<StatusPage />);
    const text = container.textContent || "";

    expect(text.toLowerCase()).not.toContain("integrity");
    expect(text.toLowerCase()).not.toContain("flag");
    expect(text.toLowerCase()).not.toContain("risk");
    expect(text.toLowerCase()).not.toContain("alert");
  });

  it("renders loading state when session is not available", () => {
    jest.resetModules();
    jest.doMock("@/context/SessionContext", () => ({
      useSession: () => ({
        state: {
          session: null,
          jwt: null,
          answers: {},
          currentIndex: 0,
          submitting: false,
        },
        dispatch: jest.fn(),
      }),
    }));

    // Re-import after mocking
    const { render: rerRender } = require("@testing-library/react");
    const StatusPageReimport = require("../page").default;

    rerRender(<StatusPageReimport />);
    expect(
      screen.getByText(/Loading your assessment status/)
    ).toBeInTheDocument();
  });

  it("renders progress bar for in_progress status", () => {
    jest.resetModules();
    jest.doMock("@/context/SessionContext", () => ({
      useSession: () => ({
        state: {
          session: {
            id: "test-session-123",
            job_title: "Senior Software Engineer",
            status: "in_progress" as const,
            seconds_remaining: 1800,
            time_budget_seconds: 2700,
            duration_minutes: 45,
            questions: [
              {
                id: "q1",
                sequence_no: 1,
                question: { text: "What is your name?" },
                category: "personal",
                target_competencies: [],
                difficulty: "easy",
                answer_format: "short_text" as const,
                options: null,
                answer_text: "John Doe",
                answered_at: "2026-07-26T10:00:00Z",
              },
              {
                id: "q2",
                sequence_no: 2,
                question: { text: "Describe your experience" },
                category: "experience",
                target_competencies: [],
                difficulty: "medium",
                answer_format: "long_text" as const,
                options: null,
                answer_text: null,
                answered_at: null,
              },
            ],
          } as SessionData,
          jwt: "test-jwt",
          answers: {},
          currentIndex: 0,
          submitting: false,
        },
        dispatch: jest.fn(),
      }),
    }));

    const { render: rerRender } = require("@testing-library/react");
    const StatusPageReimport = require("../page").default;

    rerRender(<StatusPageReimport />);
    expect(screen.getByText(/Questions Answered/)).toBeInTheDocument();
  });
});

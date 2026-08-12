import { render, screen, fireEvent } from "@testing-library/react";
import { SessionProvider, useSession } from "../SessionContext";
import type { SessionData } from "@/lib/types";

const baseSession: SessionData = {
  id: "session-1",
  status: "in_progress",
  seconds_remaining: 100,
  time_budget_seconds: 600,
  job_title: "Web Developer",
  duration_minutes: 10,
  questions: [
    {
      id: "q1",
      sequence_no: 1,
      question: { text: "Pick one" },
      category: "disc",
      target_competencies: [],
      difficulty: "medium",
      answer_format: "multiple_choice",
      options: { A: "Option A", B: "Option B" },
      answer_text: "Option A",
      answered_at: "2026-08-01T00:00:00Z",
    },
    {
      id: "q2",
      sequence_no: 2,
      question: { text: "Pick two" },
      category: "disc",
      target_competencies: [],
      difficulty: "medium",
      answer_format: "multiple_choice",
      options: { A: "Option A", B: "Option B" },
      answer_text: null,
      answered_at: null,
    },
  ],
};

function Harness() {
  const { state, dispatch } = useSession();
  return (
    <div>
      <div data-testid="jwt">{state.jwt ?? "none"}</div>
      <div data-testid="index">{state.currentIndex}</div>
      <div data-testid="submitting">{String(state.submitting)}</div>
      <div data-testid="answer-q2">{state.answers.q2 ?? "unanswered"}</div>
      <div data-testid="answer-q1">{state.answers.q1 ?? "unanswered"}</div>
      <div data-testid="adaptive-answer-q1">{state.adaptiveAnswers.q1 ?? "unanswered"}</div>
      <button onClick={() => dispatch({ type: "SET_JWT", jwt: "token-abc" })}>set-jwt</button>
      <button onClick={() => dispatch({ type: "SET_SESSION", session: baseSession })}>
        set-session
      </button>
      <button onClick={() => dispatch({ type: "REHYDRATE", session: baseSession })}>
        rehydrate
      </button>
      <button onClick={() => dispatch({ type: "SET_ANSWER", questionId: "q2", text: "Option B" })}>
        answer-q2
      </button>
      <button
        onClick={() =>
          dispatch({ type: "SET_ADAPTIVE_ANSWER", questionId: "q1", text: "Option B" })
        }
      >
        adaptive-answer-q1
      </button>
      <button onClick={() => dispatch({ type: "SET_INDEX", index: 1 })}>set-index</button>
      <button onClick={() => dispatch({ type: "SET_SUBMITTING", value: true })}>
        set-submitting
      </button>
    </div>
  );
}

function renderHarness() {
  render(
    <SessionProvider>
      <Harness />
    </SessionProvider>
  );
}

describe("SessionContext reducer", () => {
  it("throws when useSession is used outside a SessionProvider", () => {
    function Bare() {
      useSession();
      return null;
    }
    const spy = jest.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Bare />)).toThrow(
      "useSession must be used within SessionProvider"
    );
    spy.mockRestore();
  });

  it("starts with the expected initial state", () => {
    renderHarness();
    expect(screen.getByTestId("jwt")).toHaveTextContent("none");
    expect(screen.getByTestId("index")).toHaveTextContent("0");
    expect(screen.getByTestId("submitting")).toHaveTextContent("false");
  });

  it("SET_JWT stores the jwt", () => {
    renderHarness();
    fireEvent.click(screen.getByText("set-jwt"));
    expect(screen.getByTestId("jwt")).toHaveTextContent("token-abc");
  });

  it("SET_ANSWER records a local answer", () => {
    renderHarness();
    fireEvent.click(screen.getByText("answer-q2"));
    expect(screen.getByTestId("answer-q2")).toHaveTextContent("Option B");
  });

  it("SET_ADAPTIVE_ANSWER records a local adaptive answer independently of the natural answer", () => {
    renderHarness();
    fireEvent.click(screen.getByText("adaptive-answer-q1"));
    expect(screen.getByTestId("adaptive-answer-q1")).toHaveTextContent("Option B");
    // the natural answer for q1 is untouched by the adaptive dispatch
    expect(screen.getByTestId("answer-q1")).toHaveTextContent("unanswered");
  });

  it("SET_INDEX and SET_SUBMITTING update their fields", () => {
    renderHarness();
    fireEvent.click(screen.getByText("set-index"));
    fireEvent.click(screen.getByText("set-submitting"));
    expect(screen.getByTestId("index")).toHaveTextContent("1");
    expect(screen.getByTestId("submitting")).toHaveTextContent("true");
  });

  it("REHYDRATE fills answers from the server without clobbering unsaved local answers", () => {
    renderHarness();
    // Answer q2 locally first — this is the "not yet in DB" answer.
    fireEvent.click(screen.getByText("answer-q2"));
    expect(screen.getByTestId("answer-q2")).toHaveTextContent("Option B");

    // Server rehydrate carries q1's saved answer, and a stale/older q2 answer.
    fireEvent.click(screen.getByText("rehydrate"));

    // q1 comes from the server since there was no local answer for it.
    expect(screen.getByTestId("answer-q1")).toHaveTextContent("Option A");
    // q2's local, unsaved answer wins over the server's.
    expect(screen.getByTestId("answer-q2")).toHaveTextContent("Option B");
  });
});

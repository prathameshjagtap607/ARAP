"use client";

import {
  createContext,
  useContext,
  useReducer,
  ReactNode,
} from "react";
import type { SessionAction, SessionState } from "@/lib/types";

const initialState: SessionState = {
  jwt: null,
  session: null,
  answers: {},
  currentIndex: 0,
  submitting: false,
};

function reducer(state: SessionState, action: SessionAction): SessionState {
  switch (action.type) {
    case "SET_JWT":
      return { ...state, jwt: action.jwt };
    case "SET_SESSION":
      return { ...state, session: action.session };
    case "REHYDRATE": {
      const serverAnswers: Record<string, string> = {};
      for (const q of action.session.questions) {
        if (q.answer_text) serverAnswers[q.id] = q.answer_text;
      }
      // Server answers fill gaps — locally unsaved answers (not yet in DB) win
      return {
        ...state,
        session: action.session,
        answers: { ...serverAnswers, ...state.answers },
      };
    }
    case "SET_ANSWER":
      return {
        ...state,
        answers: { ...state.answers, [action.questionId]: action.text },
      };
    case "SET_INDEX":
      return { ...state, currentIndex: action.index };
    case "SET_SUBMITTING":
      return { ...state, submitting: action.value };
    default:
      return state;
  }
}

const SessionContext = createContext<{
  state: SessionState;
  dispatch: React.Dispatch<SessionAction>;
} | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  return (
    <SessionContext.Provider value={{ state, dispatch }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}

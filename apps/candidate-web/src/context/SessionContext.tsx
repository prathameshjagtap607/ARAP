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
  adaptiveAnswers: {},
  rankingOrders: {},
  reflectionTexts: {},
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
      const serverAdaptiveAnswers: Record<string, string> = {};
      const serverRankingOrders: Record<string, string[]> = {};
      const serverReflectionTexts: Record<string, string> = {};
      for (const q of action.session.questions) {
        if (q.answer_text) serverAnswers[q.id] = q.answer_text;
        if (q.adaptive_answer_text) serverAdaptiveAnswers[q.id] = q.adaptive_answer_text;
        if (q.ranking_order) serverRankingOrders[q.id] = q.ranking_order;
        if (q.reflection_text) serverReflectionTexts[q.id] = q.reflection_text;
      }
      // Server answers fill gaps — locally unsaved answers (not yet in DB) win
      return {
        ...state,
        session: action.session,
        answers: { ...serverAnswers, ...state.answers },
        adaptiveAnswers: { ...serverAdaptiveAnswers, ...state.adaptiveAnswers },
        rankingOrders: { ...serverRankingOrders, ...state.rankingOrders },
        reflectionTexts: { ...serverReflectionTexts, ...state.reflectionTexts },
      };
    }
    case "SET_ANSWER":
      return {
        ...state,
        answers: { ...state.answers, [action.questionId]: action.text },
      };
    case "SET_ADAPTIVE_ANSWER":
      return {
        ...state,
        adaptiveAnswers: { ...state.adaptiveAnswers, [action.questionId]: action.text },
      };
    case "SET_RANKING_ORDER":
      return {
        ...state,
        rankingOrders: { ...state.rankingOrders, [action.questionId]: action.order },
      };
    case "SET_REFLECTION_TEXT":
      return {
        ...state,
        reflectionTexts: { ...state.reflectionTexts, [action.questionId]: action.text },
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

export function SessionProviderWrapper({ children }: { children: ReactNode }) {
  return <SessionProvider>{children}</SessionProvider>;
}

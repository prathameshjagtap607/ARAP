"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import type { ConsoleUser } from "@/types/auth";

interface AuthState {
  user: ConsoleUser | null;
  accessToken: string | null;
}

interface AuthContextValue extends AuthState {
  setAuth: (user: ConsoleUser, accessToken: string) => void;
  clearAuth: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
  });

  const setAuth = useCallback((user: ConsoleUser, accessToken: string) => {
    setState({ user, accessToken });
  }, []);

  const clearAuth = useCallback(() => {
    setState({ user: null, accessToken: null });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, setAuth, clearAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

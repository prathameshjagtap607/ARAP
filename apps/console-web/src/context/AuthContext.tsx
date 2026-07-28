"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";
import type { ConsoleUser } from "@/types/auth";
import { refresh } from "@/lib/auth";

interface AuthState {
  user: ConsoleUser | null;
  accessToken: string | null;
  loading: boolean;
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
    loading: true,
  });

  // Initialize with loading: false (no session restore on mount)
  // Users will need to login fresh after page refresh
  useEffect(() => {
    setState(prev => ({ ...prev, loading: false }));
  }, []);

  const setAuth = useCallback((user: ConsoleUser, accessToken: string) => {
    setState({ user, accessToken, loading: false });
    // Make token available to API client
    import("@/lib/api").then(({ setGlobalAccessToken }) => {
      setGlobalAccessToken(accessToken);
    });
  }, []);

  const clearAuth = useCallback(() => {
    setState({ user: null, accessToken: null, loading: false });
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

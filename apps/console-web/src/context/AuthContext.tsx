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

  // Restore session on mount
  useEffect(() => {
    const restoreSession = async () => {
      try {
        const result = await refresh();
        setState({ user: result.user, accessToken: result.accessToken, loading: false });
        // Make token available to API client
        import("@/lib/api").then(({ setGlobalAccessToken }) => {
          setGlobalAccessToken(result.accessToken);
        });
      } catch {
        setState({ user: null, accessToken: null, loading: false });
      }
    };
    restoreSession();
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

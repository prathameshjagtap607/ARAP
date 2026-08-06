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
import { decodeToken, refresh } from "@/lib/auth";
import { setGlobalAccessToken } from "@/lib/api/index";

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

const STORAGE_KEY = "arap_auth_token";
const USER_STORAGE_KEY = "arap_auth_user";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    loading: true,
  });

  // Restore session from localStorage on mount
  useEffect(() => {
    const restore = async () => {
      try {
        const savedToken = localStorage.getItem(STORAGE_KEY);
        const savedUser = localStorage.getItem(USER_STORAGE_KEY);

        if (savedToken && savedUser) {
          try {
            const decoded = decodeToken(savedToken);
            const isExpired = decoded.exp && decoded.exp * 1000 < Date.now();
            if (isExpired) throw new Error("expired");
            const user = JSON.parse(savedUser) as ConsoleUser;
            setGlobalAccessToken(savedToken);
            setState({ user, accessToken: savedToken, loading: false });
          } catch {
            // Token missing/expired/corrupt — try a silent refresh before
            // giving up, so a page reload doesn't log the user out just
            // because the 15-minute access token happened to expire.
            try {
              const { user, accessToken } = await refresh();
              setGlobalAccessToken(accessToken);
              localStorage.setItem(STORAGE_KEY, accessToken);
              localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
              setState({ user, accessToken, loading: false });
            } catch {
              localStorage.removeItem(STORAGE_KEY);
              localStorage.removeItem(USER_STORAGE_KEY);
              setState(prev => ({ ...prev, loading: false }));
            }
          }
        } else {
          setState(prev => ({ ...prev, loading: false }));
        }
      } catch {
        setState(prev => ({ ...prev, loading: false }));
      }
    };

    restore();
  }, []);

  const setAuth = useCallback((user: ConsoleUser, accessToken: string) => {
    setState({ user, accessToken, loading: false });
    setGlobalAccessToken(accessToken);
    localStorage.setItem(STORAGE_KEY, accessToken);
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
  }, []);

  const clearAuth = useCallback(() => {
    setState({ user: null, accessToken: null, loading: false });
    setGlobalAccessToken(null);
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(USER_STORAGE_KEY);
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

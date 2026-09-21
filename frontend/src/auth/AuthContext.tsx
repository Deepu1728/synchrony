import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { fetchMe, requestLogin } from "../api/auth";
import { ApiError, onUnauthorized } from "../api/client";
import type { User } from "../api/types";
import { clearToken, getToken, setToken } from "./token";

type Status = "loading" | "anonymous" | "authenticated" | "unavailable";
type State = { status: Status; user: User | null };

type AuthValue = {
  status: Status;
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  retry: () => void;
};

const AuthContext = createContext<AuthValue | null>(null);

const ANONYMOUS: State = { status: "anonymous", user: null };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>(() => ({ status: getToken() ? "loading" : "anonymous", user: null }));
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    onUnauthorized(() => setState(ANONYMOUS));
    return () => onUnauthorized(null);
  }, []);

  useEffect(() => {
    if (!getToken()) return;
    let cancelled = false;
    setState((s) => (s.status === "authenticated" ? s : { status: "loading", user: null }));
    fetchMe()
      .then((user) => {
        if (!cancelled) setState({ status: "authenticated", user });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          clearToken();
          setState(ANONYMOUS);
        } else {
          setState({ status: "unavailable", user: null });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const login = useCallback(async (username: string, password: string) => {
    const token = await requestLogin(username, password);
    setToken(token.access_token);
    try {
      setState({ status: "authenticated", user: await fetchMe() });
    } catch (error) {
      clearToken();
      throw error;
    }
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setState(ANONYMOUS);
  }, []);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  const value = useMemo(() => ({ ...state, login, logout, retry }), [state, login, logout, retry]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}

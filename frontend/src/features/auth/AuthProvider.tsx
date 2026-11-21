import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { fetchMe, login as loginRequest, register as registerRequest } from "@/services/api/auth";
import { HttpError } from "@/services/api/apiClient";
import {
  clearAccessToken,
  getAccessToken,
  onUnauthorized,
  setAccessToken,
} from "@/services/api/authToken";
import type { LoginPayload, RegisterPayload, RoleName, User } from "@/types/auth";
import { AuthContext, type AuthContextValue, type AuthStatus } from "./AuthContext";

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>(() =>
    getAccessToken() ? "loading" : "anonymous",
  );
  const [user, setUser] = useState<User | null>(null);
  const [attempt, setAttempt] = useState(0);

  const clearSession = useCallback(() => {
    clearAccessToken();
    setUser(null);
    setStatus("anonymous");
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    if (!getAccessToken()) return;
    let cancelled = false;
    fetchMe()
      .then((me) => {
        if (cancelled) return;
        setUser(me);
        setStatus("authenticated");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof HttpError && error.status === 401) {
          clearSession();
        } else {
          setStatus("unavailable");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [attempt, clearSession]);

  useEffect(() => onUnauthorized(clearSession), [clearSession]);

  const login = useCallback(async (payload: LoginPayload) => {
    const session = await loginRequest(payload);
    setAccessToken(session.access_token);
    setUser(session.user);
    setStatus("authenticated");
  }, []);

  const register = useCallback(
    async (payload: RegisterPayload) => {
      await registerRequest(payload);
      await login({ email: payload.email, password: payload.password });
    },
    [login],
  );

  const retry = useCallback(() => {
    setStatus("loading");
    setAttempt((n) => n + 1);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      login,
      register,
      logout: clearSession,
      retry,
      hasRole: (role: RoleName) => user?.roles.includes(role) ?? false,
    }),
    [status, user, login, register, clearSession, retry],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
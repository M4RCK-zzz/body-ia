import type { AuthSession, LoginPayload, RegisterPayload, User } from "@/types/auth";
import { apiRequest } from "./apiClient";

const BASE = "/api/auth";

export function login(payload: LoginPayload): Promise<AuthSession> {
  return apiRequest<AuthSession>(`${BASE}/login`, {
    method: "POST",
    body: payload,
    skipAuth: true,
  });
}

export function register(payload: RegisterPayload): Promise<User> {
  return apiRequest<User>(`${BASE}/register`, {
    method: "POST",
    body: payload,
    skipAuth: true,
  });
}

export function fetchMe(): Promise<User> {
  return apiRequest<User>(`${BASE}/me`);
}

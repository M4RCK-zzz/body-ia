import { createContext } from "react";
import type { LoginPayload, RegisterPayload, RoleName, User } from "@/types/auth";

export type AuthStatus = "loading" | "authenticated" | "anonymous" | "unavailable";

export interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => void;
  retry: () => void;
  hasRole: (role: RoleName) => boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
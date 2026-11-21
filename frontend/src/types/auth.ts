export type RoleName = "admin" | "professional" | "user";

export interface User {
  id: string;
  email: string;
  full_name: string;
  roles: RoleName[];
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload extends LoginPayload {
  full_name: string;
}

export interface AuthSession {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}
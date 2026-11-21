export type AccessLevel = "owner" | "editor" | "viewer";
export type GrantableLevel = Exclude<AccessLevel, "owner">;

export const ACCESS_LABELS: Record<AccessLevel, string> = {
  owner: "Propietario",
  editor: "Editor",
  viewer: "Lector",
};

export interface AccessEntry {
  user_id: string;
  email: string;
  full_name: string;
  level: AccessLevel;
  granted_at: string;
}

export interface AccessGrantPayload {
  email: string;
  level: GrantableLevel;
}

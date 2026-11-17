export type ProfileStatus = "active" | "archived" | "restricted";

export interface Profile {
  id: string;
  display_code: string;
  status: ProfileStatus;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export const PROFILE_STATUS_LABEL: Record<ProfileStatus, string> = {
  active: "Activo",
  archived: "Archivado",
  restricted: "Restringido",
};
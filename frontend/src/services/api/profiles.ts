import type { Page } from "@/types/common";
import type { Profile, ProfileStatus } from "@/types/profile";
import { apiRequest } from "./apiClient";

export const profilesApi = {
  list: (status?: ProfileStatus) =>
    apiRequest<Page<Profile>>("/api/profiles", { query: { status, limit: 200 } }),
  get: (id: string) => apiRequest<Profile>(`/api/profiles/${id}`),
  create: (display_code: string) =>
    apiRequest<Profile>("/api/profiles", { method: "POST", body: { display_code } }),
  archive: (id: string) => apiRequest<Profile>(`/api/profiles/${id}/archive`, { method: "POST" }),
  restore: (id: string) => apiRequest<Profile>(`/api/profiles/${id}/restore`, { method: "POST" }),
};
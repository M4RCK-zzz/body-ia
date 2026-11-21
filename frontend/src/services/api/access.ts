import type { AccessEntry, AccessGrantPayload } from "../../types/access";
import { apiRequest } from "./apiClient";

export const accessApi = {
  list: (profileId: string) =>
    apiRequest<AccessEntry[]>(`/api/profiles/${profileId}/access`),
  grant: (profileId: string, payload: AccessGrantPayload) =>
    apiRequest<AccessEntry>(`/api/profiles/${profileId}/access`, {
      method: "POST",
      body: payload,
    }),
  revoke: (profileId: string, userId: string) =>
    apiRequest<void>(`/api/profiles/${profileId}/access/${userId}`, {
      method: "DELETE",
    }),
};

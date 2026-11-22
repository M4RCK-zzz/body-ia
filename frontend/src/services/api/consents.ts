import type { ConsentDocument, ConsentPurpose, ConsentRecord, ConsentStatus } from "@/types/consent";
import { apiRequest } from "./apiClient";

export const consentsApi = {
  documents: () => apiRequest<ConsentDocument[]>("/api/consents/documents"),
  statuses: (profileId: string) =>
    apiRequest<ConsentStatus[]>(`/api/profiles/${profileId}/consents`),
  accept: (profileId: string, purpose: ConsentPurpose) =>
    apiRequest<ConsentRecord>(`/api/profiles/${profileId}/consents`, {
      method: "POST",
      body: { purpose, declaration: true },
    }),
  revoke: (profileId: string, purpose: ConsentPurpose) =>
    apiRequest<ConsentRecord>(`/api/profiles/${profileId}/consents/${purpose}/revoke`, {
      method: "POST",
    }),
};

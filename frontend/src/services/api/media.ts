import type { MediaAsset, MediaStatus } from "@/types/media";
import type { Page } from "@/types/common";
import { apiRequest } from "./apiClient";

const profileBase = (profileId: string) => `/api/profiles/${profileId}/media`;
const assetBase = (assetId: string) => `/api/media/${assetId}`;

export const mediaApi = {
  upload: (profileId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiRequest<MediaAsset>(profileBase(profileId), {
      method: "POST",
      body: form,
      timeoutMs: 120_000,
    });
  },
  list: (profileId: string, status?: MediaStatus) =>
    apiRequest<Page<MediaAsset>>(profileBase(profileId), {
      query: { status, limit: 100 },
    }),
  get: (assetId: string) => apiRequest<MediaAsset>(assetBase(assetId)),
  content: (assetId: string) =>
    apiRequest<Blob>(`${assetBase(assetId)}/content`, { blob: true, timeoutMs: 30_000 }),
  delete: (assetId: string) =>
    apiRequest<MediaAsset>(assetBase(assetId), { method: "DELETE" }),
};

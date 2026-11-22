import type { Page } from "@/types/common";
import type { PoseAnalysis, PoseAnalysisStatus } from "@/types/pose";
import { apiRequest } from "./apiClient";

const assetBase = (assetId: string) => `/api/media/${assetId}/pose-analyses`;
const profileBase = (profileId: string) => `/api/profiles/${profileId}/pose-analyses`;
const analysisPath = (analysisId: string) => `/api/pose-analyses/${analysisId}`;

export const poseApi = {
  enqueue: (assetId: string) =>
    apiRequest<PoseAnalysis>(assetBase(assetId), { method: "POST" }),
  get: (analysisId: string) => apiRequest<PoseAnalysis>(analysisPath(analysisId)),
  listForAsset: (assetId: string, status?: PoseAnalysisStatus) =>
    apiRequest<Page<PoseAnalysis>>(assetBase(assetId), { query: { status, limit: 50 } }),
  listForProfile: (profileId: string, status?: PoseAnalysisStatus) =>
    apiRequest<Page<PoseAnalysis>>(profileBase(profileId), {
      query: { status, limit: 100 },
    }),
};

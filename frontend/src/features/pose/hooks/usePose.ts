import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { poseApi } from "@/services/api/pose";
import type { PoseAnalysis, PoseAnalysisStatus } from "@/types/pose";

export const poseKeys = {
  all: ["pose"] as const,
  asset: (assetId: string) => ["pose", "asset", assetId] as const,
  profile: (profileId: string) => ["pose", "profile", profileId] as const,
  detail: (id: string) => ["pose", "detail", id] as const,
};

export function usePoseFromAsset(assetId: string, status?: PoseAnalysisStatus) {
  return useQuery({
    queryKey: [...poseKeys.asset(assetId), status ?? "all"],
    queryFn: () => poseApi.listForAsset(assetId, status),
    enabled: assetId !== "",
    // Refrescar hasta que el análisis llegue a un estado terminal.
    refetchInterval: (query) => {
      const items = query.state.data?.items;
      if (!items?.length) return false;
      const anyActive = items.some((a) => a.status === "queued" || a.status === "processing");
      return anyActive ? 3_000 : false;
    },
  });
}

export function usePoseFromProfile(profileId: string, status?: PoseAnalysisStatus) {
  return useQuery({
    queryKey: [...poseKeys.profile(profileId), status ?? "all"],
    queryFn: () => poseApi.listForProfile(profileId, status),
    enabled: profileId !== "",
    refetchInterval: (query) => {
      const items = query.state.data?.items;
      if (!items?.length) return false;
      const anyActive = items.some((a) => a.status === "queued" || a.status === "processing");
      return anyActive ? 3_000 : false;
    },
  });
}

export function usePoseDetail(analysisId: string) {
  return useQuery({
    queryKey: poseKeys.detail(analysisId),
    queryFn: () => poseApi.get(analysisId),
    enabled: analysisId !== "",
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "processing" ? 3_000 : false;
    },
  });
}

export function useEnqueuePose(assetId: string, profileId?: string) {
  const client = useQueryClient();
  return useMutation<PoseAnalysis, Error, void>({
    mutationFn: () => poseApi.enqueue(assetId),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: poseKeys.asset(assetId) });
      if (profileId) client.invalidateQueries({ queryKey: poseKeys.profile(profileId) });
    },
  });
}

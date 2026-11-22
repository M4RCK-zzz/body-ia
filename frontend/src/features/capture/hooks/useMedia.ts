import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { mediaApi } from "@/services/api/media";
import type { MediaAsset, MediaStatus } from "@/types/media";

const assetsKey = (profileId: string) => ["capture", profileId] as const;

export function useMediaAssets(profileId: string, status?: MediaStatus) {
  return useQuery({
    queryKey: [...assetsKey(profileId), "assets", status ?? "all"],
    queryFn: () => mediaApi.list(profileId, status),
    enabled: profileId !== "",
  });
}

export function useMediaContent(assetId: string | null) {
  return useQuery({
    queryKey: ["capture", "content", assetId],
    queryFn: () => mediaApi.content(assetId as string),
    enabled: assetId !== null && assetId !== "",
    staleTime: Infinity,
  });
}

export function useUploadMedia(profileId: string) {
  const client = useQueryClient();
  return useMutation<MediaAsset, Error, File>({
    mutationFn: (file) => mediaApi.upload(profileId, file),
    onSuccess: () => client.invalidateQueries({ queryKey: assetsKey(profileId) }),
  });
}

export function useDeleteMedia(profileId: string) {
  const client = useQueryClient();
  return useMutation<MediaAsset, Error, string>({
    mutationFn: (assetId) => mediaApi.delete(assetId),
    onSuccess: () => client.invalidateQueries({ queryKey: assetsKey(profileId) }),
  });
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { profilesApi } from "@/services/api/profiles";
import type { Profile, ProfileStatus } from "@/types/profile";

export const profileKeys = {
  all: ["profiles"] as const,
  list: (status?: ProfileStatus) => ["profiles", "list", status ?? "all"] as const,
  detail: (id: string) => ["profiles", "detail", id] as const,
};

export function useProfileList(status?: ProfileStatus) {
  return useQuery({ queryKey: profileKeys.list(status), queryFn: () => profilesApi.list(status) });
}

export function useProfile(id: string) {
  return useQuery({
    queryKey: profileKeys.detail(id),
    queryFn: () => profilesApi.get(id),
    enabled: id !== "",
  });
}

export function useCreateProfile() {
  const client = useQueryClient();
  return useMutation<Profile, Error, string>({
    mutationFn: (code) => profilesApi.create(code),
    onSuccess: () => client.invalidateQueries({ queryKey: profileKeys.all }),
  });
}

export function useProfileStatusChange() {
  const client = useQueryClient();
  return useMutation<Profile, Error, { id: string; action: "archive" | "restore" }>({
    mutationFn: ({ id, action }) =>
      action === "archive" ? profilesApi.archive(id) : profilesApi.restore(id),
    onSuccess: () => client.invalidateQueries({ queryKey: profileKeys.all }),
  });
}
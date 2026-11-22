import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { consentsApi } from "@/services/api/consents";
import type { ConsentPurpose, ConsentRecord } from "@/types/consent";

const statusesKey = (profileId: string) => ["consents", profileId, "statuses"] as const;

export function useConsentDocuments(enabled: boolean) {
  return useQuery({
    queryKey: ["consents", "documents"],
    queryFn: consentsApi.documents,
    staleTime: Infinity,
    enabled,
  });
}

export function useConsentStatuses(profileId: string) {
  return useQuery({
    queryKey: statusesKey(profileId),
    queryFn: () => consentsApi.statuses(profileId),
    enabled: profileId !== "",
  });
}

export function useAcceptConsent(profileId: string) {
  const client = useQueryClient();
  return useMutation<ConsentRecord, Error, ConsentPurpose>({
    mutationFn: (purpose) => consentsApi.accept(profileId, purpose),
    onSuccess: () => client.invalidateQueries({ queryKey: statusesKey(profileId) }),
  });
}

export function useRevokeConsent(profileId: string) {
  const client = useQueryClient();
  return useMutation<ConsentRecord, Error, ConsentPurpose>({
    mutationFn: (purpose) => consentsApi.revoke(profileId, purpose),
    onSuccess: () => client.invalidateQueries({ queryKey: statusesKey(profileId) }),
  });
}

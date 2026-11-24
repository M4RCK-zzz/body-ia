import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { analyticsApi, reportsApi } from "@/services/api/reports";
import type { AnalyticsWindow } from "@/types/analytics";
import type { ReportRequestPayload, ReportStatus } from "@/types/report";
import { downloadReport } from "../download";

const root = ["reports"] as const;
const analyticsRoot = (profileId: string) => ["analytics", profileId] as const;

export function useMyReports(status?: ReportStatus) {
  return useQuery({
    queryKey: [...root, "mine", status ?? "all"],
    queryFn: () => reportsApi.listMine(status),
    // La generación es asíncrona: mientras haya trabajos abiertos se refresca.
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some((r) => r.status === "queued" || r.status === "processing") ? 4000 : false;
    },
  });
}

export function useProfileReports(profileId: string, status?: ReportStatus) {
  return useQuery({
    queryKey: [...root, "profile", profileId, status ?? "all"],
    queryFn: () => reportsApi.listForProfile(profileId, status),
    enabled: Boolean(profileId),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some((r) => r.status === "queued" || r.status === "processing") ? 4000 : false;
    },
  });
}

export function useReport(reportId: string) {
  return useQuery({
    queryKey: [...root, "detail", reportId],
    queryFn: () => reportsApi.get(reportId),
    enabled: Boolean(reportId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "processing" ? 3000 : false;
    },
  });
}

export function useAnalytics(profileId: string, windowDays: AnalyticsWindow) {
  return useQuery({
    queryKey: [...analyticsRoot(profileId), windowDays],
    queryFn: () => analyticsApi.summary(profileId, windowDays),
    enabled: Boolean(profileId),
  });
}

export function useRequestReport(profileId: string) {
  const client = useQueryClient();
  return useMutation<import("@/types/report").Report, Error, ReportRequestPayload>({
    mutationFn: (payload) => reportsApi.request(profileId, payload),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: root });
      client.invalidateQueries({ queryKey: analyticsRoot(profileId) });
    },
  });
}

export function useDownloadReport() {
  const client = useQueryClient();
  return useMutation<void, Error, { reportId: string; filename: string; checksum: string | null }>({
    mutationFn: async ({ reportId, filename, checksum }) => {
      const blob = await reportsApi.content(reportId);
      if (checksum) {
        // Verificación de integridad en el cliente (el servidor también la hace).
        const digest = await sha256Hex(blob);
        if (digest !== checksum) {
          throw new Error("El archivo descargado no coincide con el checksum registrado.");
        }
      }
      saveBlob(blob, filename);
    },
    onSuccess: () => client.invalidateQueries({ queryKey: root }),
  });
}

async function sha256Hex(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function saveBlob(blob: Blob, filename: string): void {
  downloadReport(blob, filename);
}

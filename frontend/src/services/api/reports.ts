import type { AnalyticsWindow, AnalyticsSummary, DashboardSummary } from "@/types/analytics";
import type { Page } from "@/types/common";
import type { Report, ReportRequestPayload, ReportStatus } from "@/types/report";
import { apiRequest } from "./apiClient";

export const analyticsApi = {
  summary: (profileId: string, windowDays: AnalyticsWindow) =>
    apiRequest<AnalyticsSummary>(`/api/profiles/${profileId}/analytics`, {
      query: { window_days: windowDays },
    }),
};

export const dashboardApi = {
  summary: () => apiRequest<DashboardSummary>("/api/dashboard/summary"),
};

export const reportsApi = {
  listMine: (status?: ReportStatus) =>
    apiRequest<Page<Report>>("/api/reports", { query: { status, limit: 100 } }),
  listForProfile: (profileId: string, status?: ReportStatus) =>
    apiRequest<Page<Report>>(`/api/profiles/${profileId}/reports`, {
      query: { status, limit: 100 },
    }),
  get: (reportId: string) => apiRequest<Report>(`/api/reports/${reportId}`),
  request: (profileId: string, payload: ReportRequestPayload) =>
    apiRequest<Report>(`/api/profiles/${profileId}/reports`, { method: "POST", body: payload }),
  /** Descarga autenticada: el binario viaja con el token del usuario, nunca por URL pública. */
  content: (reportId: string) =>
    apiRequest<Blob>(`/api/reports/${reportId}/content`, { blob: true, timeoutMs: 60_000 }),
};

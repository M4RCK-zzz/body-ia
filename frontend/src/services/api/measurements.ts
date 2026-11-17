import type { Page } from "@/types/common";
import type {
  Measurement, MeasurementCorrectionPayload, MeasurementCreatePayload, MeasurementSeries, MeasurementType,
} from "@/types/measurement";
import { apiRequest } from "./apiClient";

const base = (profileId: string) => `/api/profiles/${profileId}/measurements`;

export const measurementsApi = {
  list: (profileId: string, metric: MeasurementType, includeSuperseded: boolean) =>
    apiRequest<Page<Measurement>>(base(profileId), {
      query: { metric_type: metric, include_superseded: includeSuperseded, limit: 200 },
    }),
  series: (profileId: string, metric: MeasurementType) =>
    apiRequest<MeasurementSeries>(`${base(profileId)}/series`, { query: { metric_type: metric } }),
  history: (profileId: string, measurementId: string) =>
    apiRequest<Measurement[]>(`${base(profileId)}/${measurementId}/history`),
  record: (profileId: string, payload: MeasurementCreatePayload) =>
    apiRequest<Measurement>(base(profileId), { method: "POST", body: payload }),
  correct: (profileId: string, measurementId: string, payload: MeasurementCorrectionPayload) =>
    apiRequest<Measurement>(`${base(profileId)}/${measurementId}/corrections`, {
      method: "POST",
      body: payload,
    }),
};
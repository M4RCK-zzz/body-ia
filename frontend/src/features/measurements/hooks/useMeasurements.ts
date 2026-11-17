import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { measurementsApi } from "@/services/api/measurements";
import type {
  Measurement, MeasurementCorrectionPayload, MeasurementCreatePayload, MeasurementType,
} from "@/types/measurement";

const root = (profileId: string) => ["measurements", profileId] as const;

export function useMeasurementList(
  profileId: string,
  metric: MeasurementType,
  includeSuperseded: boolean,
) {
  return useQuery({
    queryKey: [...root(profileId), "list", metric, includeSuperseded],
    queryFn: () => measurementsApi.list(profileId, metric, includeSuperseded),
  });
}

export function useMeasurementSeries(profileId: string, metric: MeasurementType) {
  return useQuery({
    queryKey: [...root(profileId), "series", metric],
    queryFn: () => measurementsApi.series(profileId, metric),
  });
}

export function useMeasurementHistory(profileId: string, measurementId: string) {
  return useQuery({
    queryKey: [...root(profileId), "history", measurementId],
    queryFn: () => measurementsApi.history(profileId, measurementId),
  });
}

export function useRecordMeasurement(profileId: string) {
  const client = useQueryClient();
  return useMutation<Measurement, Error, MeasurementCreatePayload>({
    mutationFn: (payload) => measurementsApi.record(profileId, payload),
    onSuccess: () => client.invalidateQueries({ queryKey: root(profileId) }),
  });
}

export function useCorrectMeasurement(profileId: string) {
  const client = useQueryClient();
  return useMutation<
    Measurement,
    Error,
    { measurementId: string; payload: MeasurementCorrectionPayload }
  >({
    mutationFn: ({ measurementId, payload }) =>
      measurementsApi.correct(profileId, measurementId, payload),
    onSuccess: () => client.invalidateQueries({ queryKey: root(profileId) }),
  });
}
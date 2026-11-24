import type { Page } from "@/types/common";
import type {
  Simulation,
  SimulationComparison,
  SimulationCreatePayload,
  SimulationLimits,
  SimulationStatus,
} from "@/types/simulation";
import { apiRequest } from "./apiClient";

export const simulationsApi = {
  limits: () => apiRequest<SimulationLimits>("/api/simulations/limits"),
  listMine: (status?: SimulationStatus) =>
    apiRequest<Page<Simulation>>("/api/simulations", { query: { status, limit: 100 } }),
  listForProfile: (profileId: string, status?: SimulationStatus) =>
    apiRequest<Page<Simulation>>(`/api/profiles/${profileId}/simulations`, {
      query: { status, limit: 100, include_archived: true },
    }),
  get: (simulationId: string) => apiRequest<Simulation>(`/api/simulations/${simulationId}`),
  create: (profileId: string, payload: SimulationCreatePayload) =>
    apiRequest<Simulation>(`/api/profiles/${profileId}/simulations`, {
      method: "POST",
      body: payload,
    }),
  run: (simulationId: string) =>
    apiRequest<Simulation>(`/api/simulations/${simulationId}/run`, { method: "POST" }),
  archive: (simulationId: string) =>
    apiRequest<Simulation>(`/api/simulations/${simulationId}/archive`, { method: "POST" }),
  comparison: (simulationId: string) =>
    apiRequest<SimulationComparison>(`/api/simulations/${simulationId}/comparison`),
};

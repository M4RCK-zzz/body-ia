import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { simulationsApi } from "@/services/api/simulations";
import type {
  Simulation,
  SimulationCreatePayload,
  SimulationStatus,
} from "@/types/simulation";

const root = ["simulations"] as const;
const profileRoot = (profileId: string) => [...root, "profile", profileId] as const;

const pendingPoll = (items: Simulation[] | undefined) =>
  items?.some((simulation) => simulation.status === "queued") ? 4000 : false;

export function useSimulationLimits() {
  return useQuery({
    queryKey: [...root, "limits"],
    queryFn: () => simulationsApi.limits(),
    staleTime: 5 * 60_000,
  });
}

export function useProfileSimulations(profileId: string, status?: SimulationStatus) {
  return useQuery({
    queryKey: [...profileRoot(profileId), status ?? "all"],
    queryFn: () => simulationsApi.listForProfile(profileId, status),
    enabled: Boolean(profileId),
    refetchInterval: (query) => pendingPoll(query.state.data?.items),
  });
}

export function useMySimulations() {
  return useQuery({
    queryKey: [...root, "mine"],
    queryFn: () => simulationsApi.listMine(),
    refetchInterval: (query) => pendingPoll(query.state.data?.items),
  });
}

export function useSimulation(simulationId: string) {
  return useQuery({
    queryKey: [...root, "detail", simulationId],
    queryFn: () => simulationsApi.get(simulationId),
    enabled: Boolean(simulationId),
    refetchInterval: (query) => (query.state.data?.status === "queued" ? 3000 : false),
  });
}

export function useSimulationComparison(simulationId: string, enabled = true) {
  return useQuery({
    queryKey: [...root, "comparison", simulationId],
    queryFn: () => simulationsApi.comparison(simulationId),
    enabled: Boolean(simulationId) && enabled,
  });
}

export function useCreateSimulation(profileId: string) {
  const client = useQueryClient();
  return useMutation<Simulation, Error, SimulationCreatePayload>({
    mutationFn: (payload) => simulationsApi.create(profileId, payload),
    onSuccess: () => client.invalidateQueries({ queryKey: root }),
  });
}

export function useRunSimulation() {
  const client = useQueryClient();
  return useMutation<Simulation, Error, string>({
    mutationFn: (simulationId) => simulationsApi.run(simulationId),
    onSuccess: () => client.invalidateQueries({ queryKey: root }),
  });
}

export function useArchiveSimulation() {
  const client = useQueryClient();
  return useMutation<Simulation, Error, string>({
    mutationFn: (simulationId) => simulationsApi.archive(simulationId),
    onSuccess: () => client.invalidateQueries({ queryKey: root }),
  });
}

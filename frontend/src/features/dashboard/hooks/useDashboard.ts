import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/services/api/reports";

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => dashboardApi.summary(),
    staleTime: 15_000,
  });
}

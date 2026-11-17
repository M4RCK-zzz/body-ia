import { useQuery } from "@tanstack/react-query";
import { catalogApi } from "@/services/api/catalog";

export function useMeasurementCatalog() {
  return useQuery({
    queryKey: ["catalog", "measurements"],
    queryFn: catalogApi.measurements,
    staleTime: Infinity,
  });
}
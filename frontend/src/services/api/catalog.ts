import type { MeasurementCatalog } from "@/types/measurement";
import { apiRequest } from "./apiClient";

export const catalogApi = {
  measurements: () => apiRequest<MeasurementCatalog>("/api/catalog/measurements"),
};
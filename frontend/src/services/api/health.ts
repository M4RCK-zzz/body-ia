import type { HealthResponse } from "@/types/health";
import { apiRequest } from "./apiClient";

export const getHealth = () =>
  apiRequest<HealthResponse>("/api/health", { skipAuth: true, timeoutMs: 5000 });

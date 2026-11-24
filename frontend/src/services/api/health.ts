import type { HealthResponse, WorkersHealth } from "@/types/health";
import { apiRequest } from "./apiClient";

export const getHealth = () =>
  apiRequest<HealthResponse>("/api/health", { skipAuth: true, timeoutMs: 5000 });

/**
 * Latidos de los workers (`pose`, `report`, `simulation`, `retention`).
 *
 * Requiere sesión: el endpoint vive detrás del router autenticado y el panel de
 * administración es su único consumidor.
 */
export const getWorkersHealth = () =>
  apiRequest<WorkersHealth>("/api/health/workers", { timeoutMs: 8000 });

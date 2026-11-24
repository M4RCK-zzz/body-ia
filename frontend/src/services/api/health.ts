import type { HealthResponse, WorkersHealth } from "@/types/health";
import { apiRequest } from "./apiClient";

export const getHealth = () =>
  apiRequest<HealthResponse>("/api/health", { skipAuth: true, timeoutMs: 5000 });

/**
 * Latidos de los workers (`pose`, `report`, `simulation`, `retention`).
 *
 * Exige rol `admin`: el backend lo protege con `require_admin` porque devuelve
 * versiones, iteraciones y `last_error` internos (401 sin sesión, 403 sin rol).
 * El panel de administración es su único consumidor; `retention` llega con
 * `continuous: false` y no altera el estado global.
 */
export const getWorkersHealth = () =>
  apiRequest<WorkersHealth>("/api/health/workers", { timeoutMs: 8000 });

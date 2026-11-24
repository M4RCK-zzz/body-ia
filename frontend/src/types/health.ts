import type { WorkersHealth } from "@/types/admin";

export interface HealthResponse {
  status: 'ok' | 'degraded'
  service: string
  version: string
  environment: string
  database: 'up' | 'down'
  timestamp: string
}

export type { WorkersHealth }

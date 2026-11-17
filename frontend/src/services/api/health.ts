import type { HealthResponse } from '@/types/health'
import { request } from './httpClient'

export const getHealth = () => request<HealthResponse>('/api/health')
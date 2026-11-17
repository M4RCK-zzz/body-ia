import { useQuery } from '@tanstack/react-query'
import { getHealth } from '@/services/api/health'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 15_000,
    retry: false,
  })
}
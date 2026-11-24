import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminApi } from "@/services/api/admin";
import { getWorkersHealth } from "@/services/api/health";
import type { AuditFilters, PageRequest, UserFilters, WorkersHealth } from "@/types/admin";
import type { RoleName, User } from "@/types/auth";

const usersRoot = (filters: UserFilters, page: PageRequest) =>
  [
    "admin",
    "users",
    filters.search ?? "",
    filters.role ?? "all",
    typeof filters.isActive === "boolean" ? filters.isActive : "all",
    page.limit,
    page.offset,
  ] as const;

const auditRoot = (filters: AuditFilters, page: PageRequest) =>
  [
    "admin",
    "audit",
    filters.action ?? "all",
    filters.actorUserId ?? "all",
    filters.since ?? "",
    filters.until ?? "",
    page.limit,
    page.offset,
  ] as const;

export function useAdminUsers(filters: UserFilters, page: PageRequest) {
  return useQuery({
    queryKey: usersRoot(filters, page),
    queryFn: () => adminApi.listUsers({ ...filters, ...page }),
    // Sin datos personales en caché más tiempo del necesario.
    staleTime: 15_000,
  });
}

export function useAuditEvents(filters: AuditFilters, page: PageRequest) {
  return useQuery({
    queryKey: auditRoot(filters, page),
    queryFn: () => adminApi.listAuditEvents({ ...filters, ...page }),
    staleTime: 15_000,
  });
}

export function useAuditActions() {
  return useQuery({
    queryKey: ["admin", "audit-actions"],
    queryFn: adminApi.listAuditActions,
    staleTime: 5 * 60_000,
    // Un despliegue sin eventos aún no tiene catálogo: no es un error de la vista.
    retry: false,
  });
}

export function useSetRoles() {
  const client = useQueryClient();
  return useMutation<User, Error, { userId: string; roles: RoleName[] }>({
    mutationFn: ({ userId, roles }) => adminApi.setRoles(userId, roles),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["admin", "users"] });
      client.invalidateQueries({ queryKey: ["admin", "audit"] });
      client.invalidateQueries({ queryKey: ["admin", "audit-actions"] });
      // Un cambio de roles puede alterar lo que el propio usuario ve.
      client.invalidateQueries({ queryKey: ["auth"] });
    },
  });
}

export function useSetUserActive() {
  const client = useQueryClient();
  return useMutation<User, Error, { userId: string; active: boolean }>({
    mutationFn: ({ userId, active }) =>
      active ? adminApi.activate(userId) : adminApi.deactivate(userId),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["admin", "users"] });
      client.invalidateQueries({ queryKey: ["admin", "audit"] });
    },
  });
}

/**
 * Latidos de los workers. Se refresca cada 30 s: es una vista de estado, no un
 * panel de control, y `/api/health/workers` no está limitado por rate limiting.
 */
export function useWorkersHealth() {
  return useQuery<WorkersHealth>({
    queryKey: ["admin", "workers"],
    queryFn: getWorkersHealth,
    refetchInterval: 30_000,
    retry: false,
    staleTime: 10_000,
  });
}

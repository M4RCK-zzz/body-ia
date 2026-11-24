import type {
  AdminUserPage,
  AuditEventPage,
  AuditFilters,
  PageRequest,
  UserFilters,
} from "@/types/admin";
import type { RoleName, User } from "@/types/auth";
import { apiRequest } from "./apiClient";

const BASE = "/api/admin";

/** Convierte la selección de roles en el cuerpo que espera el backend. */
function rolesPayload(roles: RoleName[]): { roles: RoleName[] } {
  return { roles };
}

export const adminApi = {
  /**
   * Listado paginado de cuentas.
   *
   * Los filtros son **opcionales y aditivos**: si no se envían, el endpoint se
   * comporta como antes (paginación simple), y el panel los manda solo cuando el
   * administrador los rellena.
   */
  listUsers: (params: PageRequest & UserFilters) =>
    apiRequest<AdminUserPage>(`${BASE}/users`, {
      query: {
        limit: params.limit,
        offset: params.offset,
        search: params.search?.trim() ? params.search.trim() : undefined,
        role: params.role,
        is_active: typeof params.isActive === "boolean" ? params.isActive : undefined,
      },
    }),

  setRoles: (userId: string, roles: RoleName[]) =>
    apiRequest<User>(`${BASE}/users/${userId}/roles`, {
      method: "PUT",
      body: rolesPayload(roles),
    }),

  activate: (userId: string) =>
    apiRequest<User>(`${BASE}/users/${userId}/activate`, { method: "POST" }),

  deactivate: (userId: string) =>
    apiRequest<User>(`${BASE}/users/${userId}/deactivate`, { method: "POST" }),

  listAuditEvents: (params: PageRequest & AuditFilters) =>
    apiRequest<AuditEventPage>(`${BASE}/audit-events`, {
      query: {
        limit: params.limit,
        offset: params.offset,
        action: params.action || undefined,
        actor_user_id: params.actorUserId || undefined,
        since: params.since || undefined,
        until: params.until || undefined,
      },
    }),

  /** Acciones realmente presentes en la tabla, para no ofrecer filtros vacíos. */
  listAuditActions: () =>
    apiRequest<{ actions: string[] }>(`${BASE}/audit-actions`),
};

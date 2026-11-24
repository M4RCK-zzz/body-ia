import type { RoleName, User } from "@/types/auth";

/** Página de `/api/admin/users` (paginación por `limit`/`offset`, como el resto de la API). */
export interface AdminUserPage {
  items: User[];
  total: number;
  limit: number;
  offset: number;
}

export type AuditDetail = Record<string, unknown> | null;

/** Un evento de `audit_events` tal y como lo expone `/api/admin/audit-events`. */
export interface AuditEvent {
  id: string;
  occurred_at: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  profile_id: string | null;
  detail: AuditDetail;
}

/** Identidad mínima de un actor; solo los presentes en la página visible. */
export interface AuditActor {
  id: string;
  email: string;
  full_name: string;
}

export interface AuditEventPage {
  items: AuditEvent[];
  total: number;
  limit: number;
  offset: number;
  actors: AuditActor[];
}

export interface UserFilters {
  search?: string;
  role?: RoleName;
  isActive?: boolean;
}

export interface AuditFilters {
  action?: string;
  actorUserId?: string;
  /** ISO 8601 en UTC; el input date del navegador se convierte antes de enviarlo. */
  since?: string;
  until?: string;
}

export interface PageRequest {
  limit: number;
  offset: number;
}

export const ROLE_ORDER: RoleName[] = ["admin", "professional", "user"];

/** Estado de un worker según `/api/health/workers`. */
export interface WorkerHealth {
  name: string;
  version: string;
  /** `false` = worker one-shot (retención): su latido se informa, no degrada. */
  continuous: boolean;
  alive: boolean;
  last_seen_at: string;
  age_seconds: number;
  iterations: number;
  last_error: string | null;
}

export interface WorkersHealth {
  status: "ok" | "degraded" | "unknown";
  stale_after_seconds: number;
  workers: WorkerHealth[];
  timestamp: string;
}

/** Los cuatro workers conocidos, en el orden en que se muestran. */
export const WORKER_LABELS: Record<string, string> = {
  pose: "Análisis de pose",
  report: "Reportes",
  simulation: "Simulación",
  retention: "Retención",
};

export const WORKER_ORDER = ["pose", "report", "simulation", "retention"] as const;

/**
 * Etiquetas legibles de las acciones de auditoría.
 *
 * El backend guarda el `StrEnum` (`app/domain/identity.py`); aquí se traduce para
 * que la tabla sea legible sin perder el código original (se muestra al lado).
 * Una acción desconocida se muestra tal cual: nunca se oculta información.
 */
export const AUDIT_ACTION_LABELS: Record<string, string> = {
  "auth.registered": "Cuenta registrada",
  "auth.login": "Inicio de sesión",
  "auth.login_failed": "Intento de sesión fallido",
  "auth.account_locked": "Cuenta bloqueada",
  "admin.roles_changed": "Roles modificados",
  "admin.user_activated": "Cuenta activada",
  "admin.user_deactivated": "Cuenta desactivada",
  "admin.bootstrapped": "Administrador inicial creado",
  "profile.created": "Expediente creado",
  "profile.renamed": "Expediente renombrado",
  "profile.archived": "Expediente archivado",
  "profile.restored": "Expediente restaurado",
  "measurement.recorded": "Medición registrada",
  "measurement.corrected": "Medición corregida",
  "access.granted": "Acceso concedido",
  "access.revoked": "Acceso revocado",
  "access.denied": "Acceso denegado",
  "consent.accepted": "Consentimiento aceptado",
  "consent.revoked": "Consentimiento revocado",
  "media.uploaded": "Captura subida",
  "media.rejected": "Captura rechazada",
  "media.deleted": "Captura eliminada",
  "media.purged": "Captura purgada por retención",
  "pose.queued": "Pose en cola",
  "pose.completed": "Pose completada",
  "pose.needs_review": "Pose pendiente de revisión",
  "pose.failed": "Pose fallida",
  "report.requested": "Reporte solicitado",
  "report.generated": "Reporte generado",
  "report.failed": "Reporte fallido",
  "report.downloaded": "Reporte descargado",
  "report.purged": "Reporte purgado por retención",
  "analytics.viewed": "Analítica consultada",
  "dashboard.viewed": "Dashboard consultado",
  "simulation.created": "Escenario creado",
  "simulation.queued": "Escenario en cola",
  "simulation.completed": "Escenario calculado",
  "simulation.failed": "Escenario fallido",
  "simulation.archived": "Escenario archivado",
  "simulation.viewed": "Escenario consultado",
  "simulation.purged": "Escenario purgado por retención",
};

export function auditActionLabel(action: string): string {
  return AUDIT_ACTION_LABELS[action] ?? action;
}

/** Acciones sensibles que conviene destacar en la tabla (no se ocultan, se marcan). */
const SENSITIVE_ACTIONS = new Set([
  "admin.roles_changed",
  "admin.user_deactivated",
  "access.revoked",
  "access.denied",
  "consent.revoked",
  "media.purged",
  "report.purged",
  "simulation.purged",
  "auth.login_failed",
  "auth.account_locked",
]);

export const isSensitiveAction = (action: string): boolean => SENSITIVE_ACTIONS.has(action);

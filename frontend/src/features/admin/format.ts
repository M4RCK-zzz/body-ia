import { auditActionLabel, WORKER_ORDER, type AuditEvent, type WorkerHealth } from "@/types/admin";

/**
 * Utilidades de presentación del panel de administración.
 *
 * Viven fuera de los componentes para que el hot reload de Vite no tenga que
 * recargar la página entera (`react-refresh/only-export-components`).
 */

/** `datetime-local` → ISO 8601 en UTC. Vacío o inválido se descarta (el backend daría 422). */
export function toIso(value: string): string | undefined {
  if (!value) return undefined;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

/** ISO → valor para un `<input type="datetime-local">` en hora local. */
export function toDateTimeLocal(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

/** Resumen legible de un evento de auditoría a partir de su `detail` (jsonb). */
export function describeEvent(event: AuditEvent): string {
  const detail = event.detail ?? {};

  if (event.action === "admin.roles_changed") {
    const after = Array.isArray(detail.after) ? detail.after.join(", ") : "—";
    const before = Array.isArray(detail.before) ? detail.before.join(", ") : "—";
    return `Roles: ${before || "—"} → ${after}`;
  }
  if (event.action === "access.denied") {
    const reason = typeof detail.reason === "string" ? detail.reason : "sin motivo registrado";
    return `Acceso denegado (${reason})`;
  }

  const parts: string[] = [];
  if (event.resource_type) {
    parts.push(
      event.resource_id
        ? `${event.resource_type} · ${event.resource_id.slice(0, 8)}`
        : event.resource_type,
    );
  }
  for (const key of ["reason", "error", "policy", "status", "level"] as const) {
    const value = detail[key];
    if (typeof value === "string" && value) parts.push(`${key}: ${value}`);
  }
  return parts.join(" · ") || auditActionLabel(event.action);
}

/** El `request_id` del middleware vive en `detail` (jsonb), no en una columna. */
export function requestIdOf(event: AuditEvent): string | null {
  const value = event.detail?.request_id;
  return typeof value === "string" && value ? value : null;
}

/** "hace 12 s", "hace 3 min", "hace 2 h": legible sin depender de una librería. */
export function humanAge(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  if (seconds < 60) return `hace ${Math.round(seconds)} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `hace ${hours} h`;
  return `hace ${Math.floor(hours / 24)} días`;
}

/** Los cuatro workers conocidos, en el orden en que se muestran. */
export function orderedWorkers(workers: WorkerHealth[]): WorkerHealth[] {
  const byName = new Map(workers.map((worker) => [worker.name, worker]));
  return WORKER_ORDER.map((name) => byName.get(name)).filter(
    (worker): worker is WorkerHealth => Boolean(worker),
  );
}

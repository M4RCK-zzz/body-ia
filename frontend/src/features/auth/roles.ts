import type { RoleName } from "@/types/auth";

export const ROLE_LABELS: Record<RoleName, string> = {
  admin: "Administrador",
  professional: "Profesional",
  user: "Usuario",
};

/**
 * Descripción de cada rol. Es la misma que usa el backend en
 * `app/domain/identity.py` (`ROLE_DESCRIPTIONS`), incluida la regla de que
 * `admin` **no** da acceso implícito a expedientes.
 */
export const ROLE_DESCRIPTIONS: Record<RoleName, string> = {
  admin: "Administra cuentas y roles. No accede a expedientes sin acceso explícito.",
  professional: "Gestiona expedientes de terceros cuando estos le conceden acceso.",
  user: "Gestiona sus propios expedientes.",
};

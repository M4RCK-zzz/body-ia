import type { RoleName } from "@/types/auth";
import { ROLE_LABELS } from "@/features/auth/roles";
import { ROLE_ORDER } from "@/types/admin";

interface RoleTagsProps {
  roles: RoleName[];
  /** Resalta el rol de administrador, que es el que da acceso a este panel. */
  highlightAdmin?: boolean;
}

export function RoleTags({ roles, highlightAdmin = true }: RoleTagsProps) {
  const sorted = [...roles].sort(
    (a, b) => ROLE_ORDER.indexOf(a) - ROLE_ORDER.indexOf(b),
  );
  return (
    <span className="admin-role-tags">
      {sorted.map((role) => (
        <span
          key={role}
          className={`bv-tag ${
            highlightAdmin && role === "admin" ? "bv-tag--admin" : "bv-tag--role"
          }`}
          title={role}
        >
          {ROLE_LABELS[role]}
        </span>
      ))}
    </span>
  );
}

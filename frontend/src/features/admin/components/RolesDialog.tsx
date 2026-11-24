import { useEffect, useId, useRef, useState } from "react";
import { ROLE_DESCRIPTIONS, ROLE_LABELS } from "@/features/auth/roles";
import { HttpError } from "@/services/api/apiClient";
import { ROLE_ORDER } from "@/types/admin";
import type { RoleName, User } from "@/types/auth";

interface RolesDialogProps {
  user: User;
  /** `true` si la fila es el propio administrador: el backend le impide quitarse `admin`. */
  isSelf: boolean;
  submitting: boolean;
  error: HttpError | Error | null;
  onClose: () => void;
  onSubmit: (roles: RoleName[]) => void;
}

/**
 * Diálogo de gestión de roles.
 *
 * Regla del backend que se refleja aquí: un usuario no puede quedarse sin roles
 * (`min_length=1`) ni un administrador quitarse el rol `admin` a sí mismo. En
 * lugar de esconder la opción y dejar que el servidor la rechace a ciegas, se
 * deshabilita con el motivo visible; si aun así llega un 422, se muestra el
 * mensaje real del backend.
 */
export function RolesDialog({
  user,
  isSelf,
  submitting,
  error,
  onClose,
  onSubmit,
}: RolesDialogProps) {
  const [selected, setSelected] = useState<RoleName[]>(user.roles);
  const titleId = useId();
  const firstRoleRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setSelected(user.roles);
  }, [user]);

  useEffect(() => {
    firstRoleRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const toggle = (role: RoleName) => {
    setSelected((current) =>
      current.includes(role) ? current.filter((r) => r !== role) : [...current, role],
    );
  };

  const wouldRemoveOwnAdmin = isSelf && !selected.includes("admin");
  const empty = selected.length === 0;
  const canSubmit = !submitting && !empty && !wouldRemoveOwnAdmin;

  return (
    <div className="admin-modal__backdrop" role="presentation" onClick={onClose}>
      <div
        className="admin-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id={titleId}>Roles de {user.full_name}</h2>
        <p className="bv-muted">{user.email}</p>

        <ul className="admin-role-list">
          {ROLE_ORDER.map((role, index) => {
            const checked = selected.includes(role);
            const locked = isSelf && role === "admin";
            const id = `${titleId}-${role}`;
            return (
              <li key={role}>
                <label className={`admin-role-option${locked ? " is-locked" : ""}`} htmlFor={id}>
                  <input
                    id={id}
                    ref={index === 0 ? firstRoleRef : undefined}
                    type="checkbox"
                    checked={checked}
                    disabled={locked || submitting}
                    onChange={() => toggle(role)}
                  />
                  <span>
                    <strong>{ROLE_LABELS[role]}</strong>
                    <small>{ROLE_DESCRIPTIONS[role]}</small>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>

        {isSelf ? (
          <p className="bv-muted">
            Es tu propia cuenta: no puedes quitarte el rol de Administrador. Para cambiarlo, otro
            administrador debe hacerlo.
          </p>
        ) : null}
        {empty ? (
          <p className="bv-alert bv-alert--warn" role="alert">
            Un usuario debe conservar al menos un rol.
          </p>
        ) : null}
        {error ? (
          <p className="bv-alert bv-alert--error" role="alert">
            {error.message}
          </p>
        ) : null}

        <div className="bv-actions">
          <button
            type="button"
            className="bv-btn bv-btn--primary"
            disabled={!canSubmit}
            onClick={() => onSubmit(selected)}
          >
            {submitting ? "Guardando…" : "Guardar roles"}
          </button>
          <button type="button" className="bv-btn" onClick={onClose} disabled={submitting}>
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}

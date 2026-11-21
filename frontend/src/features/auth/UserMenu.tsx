import { useAuth } from "./useAuth";
import { ROLE_LABELS } from "./roles";
import "./auth.css";

export function UserMenu() {
  const { user, logout } = useAuth();
  if (!user) return null;
  return (
    <div className="bv-usermenu">
      <div>
        <strong>{user.full_name}</strong>
        <small>{user.roles.map((role) => ROLE_LABELS[role]).join(" · ")}</small>
      </div>
      <button type="button" onClick={logout}>
        Cerrar sesión
      </button>
    </div>
  );
}
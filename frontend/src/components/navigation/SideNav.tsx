import { NavLink } from "react-router-dom";
import { useAuth } from "@/features/auth/useAuth";
import type { RoleName } from "@/types/auth";

interface NavItem {
  label: string;
  to: string;
  /** Si se indica, el enlace solo se muestra a quien tenga alguno de estos roles. */
  roles?: RoleName[];
}

const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", to: "/" },
  { label: "Expedientes", to: "/expedientes" },
  { label: "Captura corporal", to: "/capture" },
  { label: "Análisis de pose", to: "/analyses" },
  { label: "Visor 3D", to: "/viewer" },
  { label: "Simulador", to: "/simulations" },
  { label: "Reportes", to: "/reports" },
  // Solo para administradores. Oculto (no deshabilitado) para el resto: la ruta
  // sigue protegida en el router y el backend responde 403 en `/api/admin/*`.
  { label: "Administración", to: "/admin", roles: ["admin"] },
];

export function SideNav() {
  const { hasRole, status } = useAuth();

  const visible = NAV_ITEMS.filter((item) =>
    item.roles ? item.roles.some((role) => hasRole(role)) : true,
  );

  return (
    <nav className="sidebar" aria-label="Navegación principal">
      <div className="brand">
        BODY<span>VISION</span> AI
      </div>
      <ul className="nav-list">
        {visible.map((item) => (
          <li key={item.label}>
            <NavLink
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) => `nav-link${isActive ? " nav-link--active" : ""}`}
            >
              {item.label}
            </NavLink>
          </li>
        ))}
        {status === "loading" ? (
          <li>
            <span className="nav-link nav-link--disabled" aria-hidden="true">
              Cargando…
            </span>
          </li>
        ) : null}
      </ul>
    </nav>
  );
}

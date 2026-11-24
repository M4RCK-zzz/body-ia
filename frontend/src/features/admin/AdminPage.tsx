import { useState } from "react";
import "@/components/ui/forms.css";
import { useSearchParams } from "react-router-dom";
import { AuditTab } from "./components/AuditTab";
import { UsersTab } from "./components/UsersTab";
import { WorkersTab } from "./components/WorkersTab";
import "./admin.css";

const TABS = [
  { id: "users", label: "Usuarios" },
  { id: "audit", label: "Auditoría" },
  { id: "workers", label: "Workers" },
] as const;

type TabId = (typeof TABS)[number]["id"];

const isTab = (value: string | null): value is TabId =>
  TABS.some((tab) => tab.id === value);

export function AdminPage() {
  // La pestaña vive en la URL (`/admin?tab=audit`): enlaces compartibles y
  // recarga sin perder el contexto, como el resto de vistas del proyecto.
  const [params, setParams] = useSearchParams();
  const requested = params.get("tab");
  const active: TabId = isTab(requested) ? requested : "users";
  const [announced, setAnnounced] = useState(false);

  const select = (tab: TabId) => {
    setAnnounced(true);
    setParams(tab === "users" ? {} : { tab }, { replace: true });
  };

  return (
    <div className="bv-page admin-page">
      <header className="bv-page__header">
        <div>
          <h1>Administración</h1>
          <p className="bv-muted">
            Cuentas, roles, auditoría y salud de los workers de esta instalación.
          </p>
        </div>
      </header>

      <p className="bv-alert bv-alert--info admin-scope-note">
        <strong>El rol de Administrador no da acceso a expedientes.</strong> Desde aquí se gestionan
        cuentas y roles, no datos corporales: para ver un expediente hace falta una concesión
        explícita de su titular, exactamente igual que para cualquier otra persona. Tampoco se
        pueden editar ni borrar eventos de auditoría.
      </p>

      <div className="bv-tabs admin-tabs" role="tablist" aria-label="Secciones de administración">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`admin-tab-${tab.id}`}
            aria-selected={active === tab.id}
            aria-controls={`admin-panel-${tab.id}`}
            aria-pressed={active === tab.id}
            className="bv-tab"
            onClick={() => select(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id={`admin-panel-${active}`}
        aria-labelledby={`admin-tab-${active}`}
        tabIndex={-1}
      >
        {active === "users" ? <UsersTab /> : null}
        {active === "audit" ? <AuditTab /> : null}
        {active === "workers" ? <WorkersTab /> : null}
      </div>

      <p className="bv-sr-only" role="status" aria-live="polite">
        {announced ? `Sección ${TABS.find((tab) => tab.id === active)?.label}` : ""}
      </p>
    </div>
  );
}

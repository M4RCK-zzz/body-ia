import { useState } from "react";
import "@/components/ui/forms.css";
import type { ProfileStatus } from "@/types/profile";
import { ProfileForm } from "./components/ProfileForm";
import { ProfileTable } from "./components/ProfileTable";
import { useProfileList } from "./hooks/useProfiles";

export function ProfilesPage() {
  const [filter, setFilter] = useState<ProfileStatus | "all">("active");
  const query = useProfileList(filter === "all" ? undefined : filter);

  return (
    <div className="bv-page">
      <header className="bv-page__header">
        <div>
          <h1>Expedientes</h1>
          <p className="bv-muted">
            Cada expediente agrupa el historial de mediciones reales de una persona.
          </p>
        </div>
        <select
          aria-label="Filtrar por estado"
          className="bv-input"
          value={filter}
          onChange={(e) => setFilter(e.target.value as ProfileStatus | "all")}
        >
          <option value="active">Activos</option>
          <option value="archived">Archivados</option>
          <option value="all">Todos</option>
        </select>
      </header>

      <p className="bv-alert bv-alert--warn">
        Entorno de desarrollo: el texto de consentimiento es un borrador pendiente de revisión
        legal. No cargues datos reales de personas.
      </p>

      <section className="bv-panel">
        <h2>Nuevo expediente</h2>
        <ProfileForm />
      </section>

      <section className="bv-panel">
        {query.isLoading ? <p className="bv-muted">Cargando…</p> : null}
        {query.error ? <p className="bv-alert bv-alert--error">{query.error.message}</p> : null}
        {query.data ? <ProfileTable rows={query.data.items} /> : null}
      </section>
    </div>
  );
}

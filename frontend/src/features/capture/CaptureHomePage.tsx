import { Link } from "react-router-dom";
import { useProfileList } from "@/features/profiles/hooks/useProfiles";
import { AccessBadge } from "@/features/access/AccessBadge";
import { PROFILE_STATUS_LABEL } from "@/types/profile";
import "./capture.css";

export function CaptureHomePage() {
  const profiles = useProfileList();

  return (
    <div className="bv-page">
      <header className="bv-page__header">
        <div>
          <h1>Captura corporal</h1>
          <p className="bv-muted">
            Las fotos son material de referencia privado: nunca se convierten en mediciones ni
            diagnósticos. Cada expediente muestra su guía, su subida y su inventario.
          </p>
        </div>
      </header>

      {profiles.isLoading ? <p className="bv-muted">Cargando expedientes…</p> : null}
      {profiles.error ? <p className="bv-alert bv-alert--error">{profiles.error.message}</p> : null}

      {profiles.data ? (
        <div className="capture-home__grid">
          {profiles.data.items.map((profile) => (
            <Link key={profile.id} to={`/capture/${profile.id}`} className="capture-home__card">
              <div className="capture-home__row">
                <strong>{profile.display_code}</strong>
                <AccessBadge level={profile.my_access} />
              </div>
              <p className="bv-muted">
                {PROFILE_STATUS_LABEL[profile.status].toUpperCase()} · clic para capturar
              </p>
            </Link>
          ))}
          {profiles.data.total === 0 ? (
            <p className="bv-muted">No tienes expedientes todavía. Créalos en Expedientes primero.</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

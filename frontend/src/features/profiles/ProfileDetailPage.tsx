import { Link, useParams } from "react-router-dom";
import "@/components/ui/forms.css";
import { MeasurementsWorkspace } from "@/features/measurements/MeasurementsWorkspace";
import { useMeasurementCatalog } from "@/features/measurements/hooks/useCatalog";
import { PROFILE_STATUS_LABEL } from "@/types/profile";
import { useProfile, useProfileStatusChange } from "./hooks/useProfiles";

export function ProfileDetailPage() {
  const { profileId = "" } = useParams();
  const profile = useProfile(profileId);
  const catalog = useMeasurementCatalog();
  const statusChange = useProfileStatusChange();

  if (profile.isLoading || catalog.isLoading) return <p className="bv-muted">Cargando…</p>;
  if (profile.error) {
    return (
      <div className="bv-page">
        <p className="bv-alert bv-alert--error">{profile.error.message}</p>
        <Link to="/expedientes">← Volver a expedientes</Link>
      </div>
    );
  }
  if (catalog.error || !profile.data || !catalog.data) {
    return <p className="bv-alert bv-alert--error">No se pudo cargar el catálogo de métricas.</p>;
  }

  const p = profile.data;
  const isActive = p.status === "active";

  return (
    <div className="bv-page">
      <header className="bv-page__header">
        <div>
          <Link to="/expedientes" className="bv-muted">← Expedientes</Link>
          <h1>
            {p.display_code}{" "}
            <span className="bv-tag bv-tag--status">{PROFILE_STATUS_LABEL[p.status].toUpperCase()}</span>
          </h1>
        </div>
        {p.status !== "restricted" ? (
          <button type="button" className={`bv-btn ${isActive ? "bv-btn--danger" : "bv-btn--primary"}`}
            disabled={statusChange.isPending}
            onClick={() => statusChange.mutate({ id: p.id, action: isActive ? "archive" : "restore" })}>
            {isActive ? "Archivar expediente" : "Restaurar expediente"}
          </button>
        ) : null}
      </header>
      {statusChange.isError ? (
        <p className="bv-alert bv-alert--error">{statusChange.error.message}</p>
      ) : null}

      <MeasurementsWorkspace profileId={p.id} catalog={catalog.data} readOnly={!isActive} />
    </div>
  );
}
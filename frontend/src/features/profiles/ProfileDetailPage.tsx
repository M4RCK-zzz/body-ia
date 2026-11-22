import { Link, useParams } from "react-router-dom";
import "@/components/ui/forms.css";
import { AccessBadge } from "@/features/access/AccessBadge";
import { AccessPanel } from "@/features/access/AccessPanel";
import { ConsentPanel } from "@/features/consent/ConsentPanel";
import { useConsentStatuses } from "@/features/consent/hooks/useConsent";
import { MeasurementsWorkspace } from "@/features/measurements/MeasurementsWorkspace";
import { useMeasurementCatalog } from "@/features/measurements/hooks/useCatalog";
import { PROFILE_STATUS_LABEL } from "@/types/profile";
import { useProfile, useProfileStatusChange } from "./hooks/useProfiles";

export function ProfileDetailPage() {
  const { profileId = "" } = useParams();
  const profile = useProfile(profileId);
  const catalog = useMeasurementCatalog();
  const consent = useConsentStatuses(profileId);
  const statusChange = useProfileStatusChange();

  if (profile.isLoading || catalog.isLoading) return <p className="bv-muted">Cargando…</p>;

  if (profile.error) {
    return (
      <div className="bv-page">
        <p className="bv-alert bv-alert--error">{profile.error.message}</p>
        <Link to="/e&larr; Expedientes">← V&larr; Volver a e&larr; Expedientes</Link>
      </div>
    );
  }

  if (catalog.error || !profile.data || !catalog.data) {
    return <p className="bv-alert bv-alert--error">No se pudo cargar el catálogo de métricas.</p>;
  }

  const p = profile.data;
  const isActive = p.status === "active";
  const isOwner = p.my_access === "owner";
  const canWrite = p.my_access !== "viewer";
  const consentValid = consent.data?.every((s) => s.valid);

  let readOnlyReason: string | undefined;
  if (!isActive) {
    readOnlyReason =
      "Expediente no activo: el historial es de solo lectura. El propietario puede restaurarlo.";
  } else if (!canWrite) {
    readOnlyReason =
      "Tienes acceso de lector: puedes consultar el historial, pero no registrar ni corregir.";
  } else if (consentValid === false) {
    readOnlyReason =
      "Falta el consentimiento vigente: no se pueden registrar ni corregir mediciones hasta que el propietario lo acepte.";
  }

  return (
    <div className="bv-page">
      <header className="bv-page__header">
        <div>
          <Link to="/e&larr; Expedientes" className="bv-muted">
            ← E&larr; Expedientes
          </Link>
          <h1>
            {p.display_code}{" "}
            <span className="bv-tag bv-tag--status">
              {PROFILE_STATUS_LABEL[p.status].toUpperCase()}
            </span>{" "}
            <AccessBadge level={p.my_access} />
          </h1>
        </div>
        {isOwner && p.status !== "restricted" ? (
          <button
            type="button"
            className={`bv-btn ${isActive ? "bv-btn--danger" : "bv-btn--primary"}`}
            disabled={statusChange.isPending}
            onClick={() =>
              statusChange.mutate({ id: p.id, action: isActive ? "archive" : "restore" })
            }
          >
            {isActive ? "Archivar expediente" : "Restaurar expediente"}
          </button>
        ) : null}
      </header>

      {statusChange.isError ? (
        <p className="bv-alert bv-alert--error">{statusChange.error.message}</p>
      ) : null}

      <ConsentPanel profileId={p.id} isOwner={isOwner} isActive={isActive} />

      <MeasurementsWorkspace
        profileId={p.id}
        catalog={catalog.data}
        readOnly={readOnlyReason !== undefined}
        readOnlyReason={readOnlyReason}
      />

      {isOwner ? (
        <div className="bv-panel">
          <AccessPanel profileId={p.id} />
        </div>
      ) : null}
    </div>
  );
}


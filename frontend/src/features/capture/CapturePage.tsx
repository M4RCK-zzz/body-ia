import { Link, useParams } from "react-router-dom";
import { useConsentStatuses } from "@/features/consent/hooks/useConsent";
import { useProfile } from "@/features/profiles/hooks/useProfiles";
import "@/components/ui/forms.css";
import { AccessBadge } from "@/features/access/AccessBadge";
import { CaptureGuide } from "./CaptureGuide";
import { CaptureList } from "./CaptureList";
import { CaptureUpload } from "./CaptureUpload";
import { useMediaAssets } from "./hooks/useMedia";
import { PROFILE_STATUS_LABEL } from "@/types/profile";
import { PoseReviewPanel } from "@/features/pose/PoseReviewPanel";
import "./capture.css";

export function CapturePage() {
  const { profileId = "" } = useParams();
  const profile = useProfile(profileId);
  const consent = useConsentStatuses(profileId);
  const assets = useMediaAssets(profileId);

  if (profile.isLoading) return <p className="bv-muted">Cargando…</p>;
  if (profile.error) {
    return (
      <div className="bv-page">
        <p className="bv-alert bv-alert--error">{profile.error.message}</p>
        <Link to="/capture" className="bv-muted">← Captura corporal</Link>
      </div>
    );
  }

  const p = profile.data;
  if (!p) return null;

  const isActive = p.status === "active";
  const canWrite = p.my_access !== "viewer";
  const consentValid = consent.data?.every((s) => s.valid);

  let readOnlyReason: string | undefined;
  if (!isActive) {
    readOnlyReason = "Expediente no activo: las capturas son de solo lectura. El propietario puede restaurarlo.";
  } else if (!canWrite) {
    readOnlyReason = "Tienes acceso de lector: puedes consultar las capturas, pero no subir ni eliminar.";
  } else if (consentValid === false) {
    readOnlyReason = "Falta el consentimiento vigente: no se pueden subir capturas. El propietario debe aceptarlo.";
  }

  return (
    <div className="bv-page">
      <header className="bv-page__header">
        <div>
          <Link to="/capture" className="bv-muted">← Captura corporal</Link>
          <h1>
            {p.display_code}{" "}
            <span className="bv-tag bv-tag--status">{PROFILE_STATUS_LABEL[p.status].toUpperCase()}</span>{" "}
            <AccessBadge level={p.my_access} />
          </h1>
        </div>
        <Link to={`/expedientes/${p.id}`} className="bv-btn bv-btn--small">
          Ver ficha de expediente
        </Link>
      </header>

      <p className="bv-alert bv-alert--warn">
        Las imágenes son <strong>material de referencia</strong>, no mediciones. No representan
        geometría ni diagnósticos. Las mediciones observadas viven en la ficha de expediente.
      </p>

      <CaptureGuide />

      <CaptureUpload profileId={p.id} readOnly={readOnlyReason !== undefined} readOnlyReason={readOnlyReason} />

      <PoseReviewPanel profileId={p.id} />

      <section className="bv-panel">
        <h2>Capturas de {p.display_code}</h2>
        {assets.isLoading ? <p className="bv-muted">Cargando capturas…</p> : null}
        {assets.error ? <p className="bv-alert bv-alert--error">{assets.error.message}</p> : null}
        {assets.data ? (
          <CaptureList
            profileId={p.id}
            assets={assets.data.items}
            total={assets.data.total}
            readOnly={readOnlyReason !== undefined}
          />
        ) : null}
      </section>
    </div>
  );
}

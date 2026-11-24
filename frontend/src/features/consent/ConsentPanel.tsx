import { useState } from "react";
import { formatDateTime } from "@/features/measurements/format";
import type { ConsentDocument, ConsentStatus } from "@/types/consent";
import {
  useAcceptConsent,
  useConsentDocuments,
  useConsentStatuses,
  useRevokeConsent,
} from "./hooks/useConsent";

interface ItemProps {
  profileId: string;
  status: ConsentStatus;
  document: ConsentDocument | undefined;
  isOwner: boolean;
  isActive: boolean;
}

function ConsentItem({ profileId, status, document, isOwner, isActive }: ItemProps) {
  const [agreed, setAgreed] = useState(false);
  const accept = useAcceptConsent(profileId);
  const revoke = useRevokeConsent(profileId);

  if (status.valid && status.current) {
    return (
      <div>
        <p className="bv-alert bv-alert--info">
          Consentimiento vigente (versión {status.current.version}), aceptado el{" "}
          {formatDateTime(status.current.accepted_at)}.
        </p>
        {isOwner ? (
          <button
            type="button"
            className="bv-btn bv-btn--small"
            disabled={revoke.isPending}
            onClick={() => {
              if (
                window.confirm(
                  "¿Revocar el consentimiento? No se podrán registrar ni corregir mediciones " +
                    "hasta aceptarlo de nuevo. Los datos existentes no se borran.",
                )
              ) {
                revoke.mutate(status.purpose);
              }
            }}
          >
            Revocar consentimiento
          </button>
        ) : null}
        {revoke.isError ? (
          <p className="bv-alert bv-alert--error" role="alert">{revoke.error.message}</p>
        ) : null}
      </div>
    );
  }

  return (
    <div>
      <p className="bv-alert bv-alert--warn">
        Sin consentimiento vigente: no se pueden registrar ni corregir mediciones.
        {status.current
          ? ` Hay una versión nueva del texto (${status.required_version}) que debe aceptarse.`
          : ""}
      </p>
      {!isOwner ? (
        <p className="bv-muted">Solo el propietario del expediente puede aceptarlo.</p>
      ) : !isActive ? (
        <p className="bv-muted">Restaura el expediente para poder aceptar el consentimiento.</p>
      ) : !document ? (
        <p className="bv-muted">Cargando texto del consentimiento…</p>
      ) : (
        <div>
          <h3>{document.title}</h3>
          <p className="bv-alert bv-alert--warn">{document.review_status}</p>
          {document.paragraphs.map((text, i) => (
            <p key={i}>{text}</p>
          ))}
          <p className="bv-muted">Versión del texto: {document.version}</p>
          <label className="bv-check">
            <input
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
            />
            <span>{document.declaration}</span>
          </label>
          <button
            type="button"
            className="bv-btn bv-btn--primary"
            disabled={!agreed || accept.isPending}
            onClick={() => accept.mutate(status.purpose)}
          >
            {accept.isPending ? "Registrando…" : "Aceptar consentimiento"}
          </button>
          {accept.isError ? (
            <p className="bv-alert bv-alert--error" role="alert">{accept.error.message}</p>
          ) : null}
        </div>
      )}
    </div>
  );
}

export function ConsentPanel({
  profileId,
  isOwner,
  isActive,
}: {
  profileId: string;
  isOwner: boolean;
  isActive: boolean;
}) {
  const statuses = useConsentStatuses(profileId);
  const needsText = isOwner && isActive && (statuses.data?.some((s) => !s.valid) ?? false);
  const documents = useConsentDocuments(needsText);

  return (
    <section className="bv-panel" aria-label="Consentimiento">
      <h2>Consentimiento</h2>
      {statuses.isLoading ? <p className="bv-muted">Cargando…</p> : null}
      {statuses.error ? (
        <p className="bv-muted">No se pudo consultar el consentimiento: {statuses.error.message}</p>
      ) : null}
      {statuses.data?.map((s) => (
        <ConsentItem
          key={s.purpose}
          profileId={profileId}
          status={s}
          document={documents.data?.find((d) => d.purpose === s.purpose)}
          isOwner={isOwner}
          isActive={isActive}
        />
      ))}
    </section>
  );
}

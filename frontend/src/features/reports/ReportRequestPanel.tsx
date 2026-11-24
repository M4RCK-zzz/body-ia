import { useState } from "react";
import { DataKindBadge } from "@/components/ui/DataKindBadge";
import {
  REPORT_KIND_HELP,
  REPORT_KIND_LABEL,
  REPORT_KINDS_MEASUREMENTS,
  REPORT_KINDS_POSE,
  type ReportKind,
} from "@/types/report";
import { useRequestReport } from "./hooks/useReports";

/**
 * Solicitud de reportes. Los de mediciones (OBSERVADO) y los de pose
 * (ESTIMACIÓN VISUAL) son documentos distintos y nunca se combinan.
 */
export function ReportRequestPanel({ profileId }: { profileId: string }) {
  const [kind, setKind] = useState<ReportKind>("measurements_csv");
  const request = useRequestReport(profileId);
  const isPose = REPORT_KINDS_POSE.includes(kind);

  return (
    <section className="bv-panel report-request">
      <h2>Solicitar reporte</h2>
      <p className="bv-muted">
        El documento se genera en segundo plano y queda trazado (quién, cuándo, qué se incluyó y su
        checksum SHA-256). Se descarga con tu sesión; nunca hay enlaces públicos.
      </p>

      <div className="report-kind-grid" role="radiogroup" aria-label="Tipo de reporte">
        <fieldset className="report-kind-group">
          <legend>
            <DataKindBadge kind="observed" /> Mediciones observadas
          </legend>
          {REPORT_KINDS_MEASUREMENTS.map((option) => (
            <label key={option} className="report-kind">
              <input
                type="radio"
                name="report-kind"
                value={option}
                checked={kind === option}
                onChange={() => setKind(option)}
              />
              <span>
                <strong>{REPORT_KIND_LABEL[option]}</strong>
                <small>{REPORT_KIND_HELP[option]}</small>
              </span>
            </label>
          ))}
        </fieldset>

        <fieldset className="report-kind-group">
          <legend>
            <DataKindBadge kind="visual_estimate" /> Estimaciones de pose
          </legend>
          {REPORT_KINDS_POSE.map((option) => (
            <label key={option} className="report-kind">
              <input
                type="radio"
                name="report-kind"
                value={option}
                checked={kind === option}
                onChange={() => setKind(option)}
              />
              <span>
                <strong>{REPORT_KIND_LABEL[option]}</strong>
                <small>{REPORT_KIND_HELP[option]}</small>
              </span>
            </label>
          ))}
        </fieldset>
      </div>

      <div className="bv-row">
        <button
          type="button"
          className="bv-btn bv-btn--primary"
          disabled={request.isPending}
          onClick={() => request.mutate({ kind })}
        >
          {request.isPending ? "Enviando…" : "Generar reporte"}
        </button>
        {request.data ? (
          <span className="report-request__ok" role="status">
            Solicitud registrada ({request.data.status === "queued" ? "en cola" : request.data.status}
            ). El worker la procesa en segundo plano.
          </span>
        ) : null}
      </div>

      {isPose ? (
        <p className="bv-alert bv-alert--warn">
          Este documento contiene <strong>estimaciones visuales</strong>, no mediciones. No se
          mezcla con los reportes de mediciones observadas.
        </p>
      ) : null}

      {request.error ? <p className="bv-alert bv-alert--error">{request.error.message}</p> : null}
    </section>
  );
}

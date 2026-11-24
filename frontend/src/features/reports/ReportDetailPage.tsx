import { Link, useParams } from "react-router-dom";
import "@/components/ui/forms.css";
import { DataKindBadge } from "@/components/ui/DataKindBadge";
import { formatDateTime } from "@/features/measurements/format";
import { REPORT_KIND_LABEL } from "@/types/report";
import { ReportStatusBadge } from "./components/ReportStatusBadge";
import { formatBytes, reportFilename } from "./download";
import { useDownloadReport, useReport } from "./hooks/useReports";

export function ReportDetailPage() {
  const { reportId = "" } = useParams();
  const report = useReport(reportId);
  const download = useDownloadReport();

  if (report.isLoading) return <p className="bv-muted">Cargando reporte…</p>;
  if (report.error) {
    return (
      <div className="bv-page">
        <p className="bv-alert bv-alert--error">{report.error.message}</p>
        <Link to="/reports">← Volver a Reportes</Link>
      </div>
    );
  }
  if (!report.data) return null;

  const r = report.data;
  const ready = r.status === "generated";

  return (
    <div className="bv-page">
      <header className="bv-page__header">
        <div>
          <Link to="/reports" className="bv-muted">
            ← Volver a Reportes
          </Link>
          <h1>{REPORT_KIND_LABEL[r.kind]}</h1>
          <div className="report-detail__badges">
            <ReportStatusBadge status={r.status} />
            <DataKindBadge kind={r.data_kind} />
            <code>{r.id.slice(0, 8)}</code>
          </div>
        </div>
        <div className="bv-actions">
          <button
            type="button"
            className="bv-btn bv-btn--primary"
            disabled={!ready || download.isPending}
            onClick={() =>
              download.mutate({
                reportId: r.id,
                filename: reportFilename(r),
                checksum: r.checksum_sha256,
              })
            }
          >
            {download.isPending ? "Descargando…" : `Descargar ${r.format.toUpperCase()}`}
          </button>
        </div>
      </header>

      {!ready ? (
        <p className="bv-alert bv-alert--info">
          {r.status === "failed"
            ? "El reporte falló y no se generó ningún archivo."
            : "El worker está generando el documento. Esta página se actualiza sola."}
        </p>
      ) : null}

      {r.error_message ? <p className="bv-alert bv-alert--error">{r.error_message}</p> : null}
      {download.error ? <p className="bv-alert bv-alert--error">{download.error.message}</p> : null}

      <section className="bv-panel">
        <h2>Trazabilidad</h2>
        <dl className="report-detail__kv">
          <dt>Expediente</dt>
          <dd>
            <Link to={`/expedientes/${r.profile_id}`}>{r.profile_id.slice(0, 8)}</Link>
          </dd>
          <dt>Solicitado por</dt>
          <dd>{r.requested_by}</dd>
          <dt>Solicitado el</dt>
          <dd>{formatDateTime(r.created_at)}</dd>
          <dt>Periodo</dt>
          <dd>
            {r.date_from ? formatDateTime(r.date_from) : "todo el historial"} –{" "}
            {r.date_to ? formatDateTime(r.date_to) : "todo el historial"}
          </dd>
          <dt>Métricas</dt>
          <dd>{r.metrics_json && r.metrics_json.length > 0 ? r.metrics_json.join(", ") : "todas"}</dd>
          <dt>Generado el</dt>
          <dd>{r.completed_at ? formatDateTime(r.completed_at) : "—"}</dd>
          <dt>Duración</dt>
          <dd>{r.duration_ms !== null ? `${r.duration_ms} ms` : "—"}</dd>
          <dt>Tamaño</dt>
          <dd>{formatBytes(r.size_bytes)}</dd>
          <dt>Checksum SHA-256</dt>
          <dd>
            <code className="report-detail__checksum">{r.checksum_sha256 ?? "—"}</code>
          </dd>
        </dl>
      </section>

      {r.summary_json ? (
        <section className="bv-panel">
          <h2>Resumen del contenido</h2>
          <pre className="report-detail__summary">{JSON.stringify(r.summary_json, null, 2)}</pre>
        </section>
      ) : null}

      <p className="analytics-disclaimer">
        <strong>Aviso:</strong> documento de registro y visualización. No es un informe clínico ni
        sustituye una valoración profesional. Las estimaciones de pose no son mediciones.
      </p>
    </div>
  );
}

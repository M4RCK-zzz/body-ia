import { useState } from "react";
import "@/components/ui/forms.css";
import { DataKindBadge } from "@/components/ui/DataKindBadge";
import type { ReportStatus } from "@/types/report";
import { ReportList } from "./components/ReportList";
import { useMyReports } from "./hooks/useReports";
import "./reports.css";

const FILTERS: { value: ReportStatus | undefined; label: string }[] = [
  { value: undefined, label: "Todos" },
  { value: "generated", label: "Listos" },
  { value: "queued", label: "En cola" },
  { value: "failed", label: "Fallidos" },
];

export function ReportsPage() {
  const [status, setStatus] = useState<ReportStatus | undefined>(undefined);
  const reports = useMyReports(status);

  return (
    <div className="bv-page">
      <header className="bv-page__header">
        <div>
          <h1>Reportes</h1>
          <p className="bv-muted">
            Documentos generados desde tus expedientes con acceso vigente. CSV y PDF; siempre con
            aviso no clínico y checksum de integridad.
          </p>
        </div>
        <div className="bv-tabs" role="group" aria-label="Filtrar por estado">
          {FILTERS.map((filter) => (
            <button
              key={filter.label}
              type="button"
              className="bv-tab"
              aria-pressed={status === filter.value}
              onClick={() => setStatus(filter.value)}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </header>

      <ul className="report-kinds-legend">
        <li>
          <DataKindBadge kind="observed" /> Mediciones observadas: valores registrados, unidades,
          método y fecha.
        </li>
        <li>
          <DataKindBadge kind="visual_estimate" /> Estimaciones de pose: inferencias visuales que{" "}
          <strong>nunca</strong> se mezclan con las mediciones.
        </li>
      </ul>

      {reports.isLoading ? <p className="bv-muted">Cargando reportes…</p> : null}
      {reports.error ? <p className="bv-alert bv-alert--error">{reports.error.message}</p> : null}
      {reports.data ? (
        <ReportList reports={reports.data.items} showRequester={false} />
      ) : null}
    </div>
  );
}

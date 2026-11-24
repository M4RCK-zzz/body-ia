import { Link } from "react-router-dom";
import { DataKindBadge } from "@/components/ui/DataKindBadge";
import { formatDateTime } from "@/features/measurements/format";
import { REPORT_KIND_LABEL, type Report } from "@/types/report";
import { formatBytes } from "../download";
import { ReportStatusBadge } from "./ReportStatusBadge";

interface Props {
  reports: Report[];
  /** Muestra la columna "Solicitado por" (vista global, no por expediente). */
  showRequester?: boolean;
}

export function ReportList({ reports, showRequester = false }: Props) {
  if (reports.length === 0) {
    return <p className="bv-muted">Todavía no hay reportes solicitados.</p>;
  }
  return (
    <ul className="report-list">
      {reports.map((report) => (
        <li key={report.id} className="report-list__row">
          <div className="report-list__main">
            <Link to={`/reports/${report.id}`} className="report-list__title">
              {REPORT_KIND_LABEL[report.kind]}
            </Link>
            <div className="report-list__meta">
              <DataKindBadge kind={report.data_kind} />
              <span>{formatDateTime(report.created_at)}</span>
              {showRequester ? <span>por {report.requested_by}</span> : null}
              {report.size_bytes !== null ? <span>{formatBytes(report.size_bytes)}</span> : null}
            </div>
          </div>
          <div className="report-list__actions">
            <ReportStatusBadge status={report.status} />
            <Link to={`/reports/${report.id}`} className="bv-btn bv-btn--small">
              Detalle
            </Link>
          </div>
        </li>
      ))}
    </ul>
  );
}

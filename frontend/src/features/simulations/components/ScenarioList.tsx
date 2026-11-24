import { Link } from "react-router-dom";
import { DataKindBadge } from "@/components/ui/DataKindBadge";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDateTime } from "@/features/measurements/format";
import { metricLabel, type MetricLabelMap } from "@/features/measurements/metricLabels";
import {
  SIMULATION_STATUS_LABEL,
  type Simulation,
  type SimulationStatus,
} from "@/types/simulation";

const VARIANT: Record<SimulationStatus, "ok" | "warn" | "error" | "neutral"> = {
  draft: "neutral",
  queued: "warn",
  completed: "ok",
  failed: "error",
  archived: "neutral",
};

interface Props {
  simulations: Simulation[];
  onArchive?: (simulation: Simulation) => void;
  archivingId?: string | null;
  /** Etiquetas del catálogo de métricas; si falta se usa la tabla en español. */
  metricLabels?: MetricLabelMap;
}

export function ScenarioList({ simulations, onArchive, archivingId, metricLabels }: Props) {
  if (simulations.length === 0) {
    return <p className="bv-muted">Todavía no hay escenarios en este expediente.</p>;
  }
  return (
    <ul className="scenario-list">
      {simulations.map((simulation) => {
        const archived = simulation.status === "archived";
        const canArchive =
          onArchive !== undefined &&
          (simulation.status === "completed" ||
            simulation.status === "failed" ||
            simulation.status === "draft");
        return (
          <li key={simulation.id} className={`scenario-list__row${archived ? " is-archived" : ""}`}>
            <div className="scenario-list__main">
              <Link to={`/simulations/${simulation.profile_id}/${simulation.id}`} className="scenario-list__title">
                {simulation.label}
              </Link>
              <div className="scenario-list__meta">
                <DataKindBadge kind="simulation" />
                <span>{formatDateTime(simulation.created_at)}</span>
                <span className="scenario-list__metrics">
                  {simulation.parameters_json.metrics
                    .map((metric) => metricLabel(metric.metric_type, metricLabels))
                    .join(", ")}
                </span>
                <span>motor {simulation.engine_version}</span>
              </div>
            </div>
            <div className="scenario-list__actions">
              <StatusBadge variant={VARIANT[simulation.status]}>
                {SIMULATION_STATUS_LABEL[simulation.status]}
              </StatusBadge>
              {simulation.status === "queued" ? (
                <span className="bv-muted scenario-list__hint">El worker lo calcula en segundo plano</span>
              ) : null}
              {canArchive ? (
                <button
                  type="button"
                  className="bv-btn bv-btn--small"
                  disabled={archivingId === simulation.id}
                  onClick={() => onArchive?.(simulation)}
                >
                  Archivar
                </button>
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

import { Link, useParams } from "react-router-dom";
import "@/components/ui/forms.css";
import { DataKindBadge } from "@/components/ui/DataKindBadge";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDateTime } from "@/features/measurements/format";
import {
  PARAMETER_MODE_LABEL,
  SIMULATION_STATUS_LABEL,
  type SimulationStatus,
} from "@/types/simulation";
import { ScenarioBanner } from "./components/ScenarioBanner";
import { ScenarioComparator } from "./components/ScenarioComparator";
import {
  useArchiveSimulation,
  useRunSimulation,
  useSimulation,
  useSimulationComparison,
} from "./hooks/useSimulations";
import "./simulations.css";

const VARIANT: Record<SimulationStatus, "ok" | "warn" | "error" | "neutral"> = {
  draft: "neutral",
  queued: "warn",
  completed: "ok",
  failed: "error",
  archived: "neutral",
};

export function SimulationDetailPage() {
  const { simulationId = "" } = useParams();
  const simulation = useSimulation(simulationId);
  const comparison = useSimulationComparison(
    simulationId,
    simulation.data?.status === "completed" || simulation.data?.status === "archived",
  );
  const run = useRunSimulation();
  const archive = useArchiveSimulation();

  if (simulation.isLoading) return <p className="bv-muted">Cargando escenario…</p>;
  if (simulation.error) {
    return (
      <div className="bv-page">
        <p className="bv-alert bv-alert--error">{simulation.error.message}</p>
        <Link to="/simulations">← Volver al simulador</Link>
      </div>
    );
  }
  if (!simulation.data) return null;

  const s = simulation.data;
  const canRun = s.status === "draft";
  const canArchive = ["draft", "completed", "failed"].includes(s.status);

  return (
    <div className="bv-page">
      <header className="bv-page__header">
        <div>
          <Link to={`/simulations/${s.profile_id}`} className="bv-muted">
            ← Volver al simulador del expediente
          </Link>
          <h1>{s.label}</h1>
          <div className="scenario-header__badges">
            <StatusBadge variant={VARIANT[s.status]}>{SIMULATION_STATUS_LABEL[s.status]}</StatusBadge>
            <DataKindBadge kind="simulation" />
            <span className="bv-muted">
              motor {s.engine_name} {s.engine_version}
            </span>
          </div>
        </div>
        <div className="bv-actions">
          {canRun ? (
            <button
              type="button"
              className="bv-btn bv-btn--primary"
              disabled={run.isPending}
              onClick={() => run.mutate(s.id)}
            >
              Calcular escenario
            </button>
          ) : null}
          {canArchive ? (
            <button
              type="button"
              className="bv-btn"
              disabled={archive.isPending}
              onClick={() => archive.mutate(s.id)}
            >
              Archivar
            </button>
          ) : null}
        </div>
      </header>

      <ScenarioBanner />

      {s.status === "queued" ? (
        <p className="bv-alert bv-alert--info">
          El worker está calculando este escenario. La página se actualiza automáticamente.
        </p>
      ) : null}
      {s.status === "failed" ? (
        <p className="bv-alert bv-alert--error">
          El escenario falló: {s.error_message ?? "sin detalle"}. Crea uno nuevo para reintentar.
        </p>
      ) : null}
      {run.error ? <p className="bv-alert bv-alert--error">{run.error.message}</p> : null}
      {archive.error ? <p className="bv-alert bv-alert--error">{archive.error.message}</p> : null}

      <section className="bv-panel">
        <h2>Parámetros solicitados</h2>
        <ul className="scenario-params">
          {s.parameters_json.metrics.map((metric) => (
            <li key={metric.metric_type}>
              <strong>{metric.metric_type}</strong> · {PARAMETER_MODE_LABEL[metric.mode]} ·{" "}
              {metric.value}
            </li>
          ))}
        </ul>
        <dl className="scenario-trace">
          <dt>Solicitado por</dt>
          <dd>{s.created_by}</dd>
          <dt>Solicitado el</dt>
          <dd>{formatDateTime(s.created_at)}</dd>
          <dt>En cola</dt>
          <dd>{s.queued_at ? formatDateTime(s.queued_at) : "—"}</dd>
          <dt>Calculado el</dt>
          <dd>{s.completed_at ? formatDateTime(s.completed_at) : "—"}</dd>
          <dt>Duración</dt>
          <dd>{s.duration_ms === null ? "—" : `${s.duration_ms} ms`}</dd>
          <dt>Archivado el</dt>
          <dd>{s.archived_at ? formatDateTime(s.archived_at) : "—"}</dd>
          <dt>Hash de la base</dt>
          <dd>
            <code>{s.baseline_hash}</code>
          </dd>
        </dl>
        {s.notes ? <p className="bv-muted">Nota: {s.notes}</p> : null}
      </section>

      {comparison.isLoading ? <p className="bv-muted">Cargando comparador…</p> : null}
      {comparison.error ? <p className="bv-alert bv-alert--error">{comparison.error.message}</p> : null}
      {comparison.data ? <ScenarioComparator comparison={comparison.data} /> : null}
    </div>
  );
}

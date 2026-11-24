import { Link } from "react-router-dom";
import {
  POSE_QUALITY_LABEL,
  POSE_STATUS_BADGE_CLASS,
  POSE_STATUS_LABEL,
  formatDurationMs,
  formatTimestamp,
  type PoseAnalysis,
} from "@/types/pose";
import { usePoseFromProfile } from "./hooks/usePose";
import "./pose.css";

/** Panel de revisión de análisis de pose de un expediente (siempre ESTIMACIÓN VISUAL). */

function AnalysisRow({ analysis }: { analysis: PoseAnalysis }) {
  const terminal = analysis.status === "completed" || analysis.status === "needs_review" || analysis.status === "failed";
  return (
    <li className="pose-list__row">
      <div className="pose-list__main">
        <div className="pose-list__row" style={{ border: 0, padding: 0, background: "transparent" }}>
          <span className={`bv-tag ${POSE_STATUS_BADGE_CLASS[analysis.status]}`}>
            {POSE_STATUS_LABEL[analysis.status].toUpperCase()}
          </span>
          <span className="pose-badge">ESTIMACIÓN VISUAL</span>
        </div>
        <p className="pose-list__meta">
          {analysis.model_version ? `Modelo ${analysis.model_version} · ` : ""}
          {terminal ? formatTimestamp(analysis.completed_at) : "En proceso…"}
          {analysis.duration_ms !== null ? ` · ${formatDurationMs(analysis.duration_ms)}` : ""}
        </p>
        {analysis.quality_flags ? (
          <p className="pose-list__meta">
            {POSE_QUALITY_LABEL[analysis.quality_flags.quality] ?? analysis.quality_flags.quality} ·{" "}
            {analysis.quality_flags.visible_landmarks}/{analysis.quality_flags.total_landmarks} landmarks visibles
          </p>
        ) : null}
        {analysis.error_message ? (
          <p className="pose-list__meta pose-list__error">{analysis.error_message}</p>
        ) : null}
      </div>
      <div className="pose-list__actions">
        <Link className="bv-btn bv-btn--small" to={`/analyses/${analysis.id}`}>
          Ver análisis
        </Link>
      </div>
    </li>
  );
}

interface Props {
  profileId: string;
}

export function PoseReviewPanel({ profileId }: Props) {
  const query = usePoseFromProfile(profileId);

  return (
    <section className="bv-panel" aria-label="Análisis de pose">
      <div className="pose-panel__header">
        <h2>Análisis de pose</h2>
        <span className="pose-badge">ESTIMACIÓN VISUAL</span>
      </div>
      <p className="bv-muted" style={{ fontSize: "0.85rem" }}>
        Resultados generados por un modelo de IA. <strong>No son mediciones ni diagnósticos</strong>.
      </p>
      {query.isLoading ? <p className="bv-muted">Cargando análisis…</p> : null}
      {query.error ? <p className="bv-alert bv-alert--error">{query.error.message}</p> : null}
      {query.data && query.data.total === 0 ? (
        <p className="bv-muted">
          Sin análisis todavía. Analiza una captura desde su tarjeta para crear uno.
        </p>
      ) : null}
      {query.data && query.data.total > 0 ? (
        <ul className="pose-list" style={{ listStyle: "none", padding: 0 }}>
          {query.data.items.map((a) => (
            <AnalysisRow key={a.id} analysis={a} />
          ))}
        </ul>
      ) : null}
      {query.data ? (
        <p className="bv-muted">{query.data.total} análisis en este expediente</p>
      ) : null}
    </section>
  );
}

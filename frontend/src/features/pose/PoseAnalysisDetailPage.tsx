import { Link, useParams } from "react-router-dom";
import {
  POSE_FLAG_LABEL,
  POSE_QUALITY_LABEL,
  POSE_STATUS_BADGE_CLASS,
  POSE_STATUS_LABEL,
  formatDurationMs,
  formatTimestamp,
  type PoseAnalysis,
} from "@/types/pose";
import { usePoseDetail } from "./hooks/usePose";
import { SkeletonPreview } from "./SkeletonPreview";
import "./pose.css";

function QualitySection({ analysis }: { analysis: PoseAnalysis }) {
  if (!analysis.quality_flags) return null;
  const flags = analysis.quality_flags.flags ?? [];
  return (
    <section className="bv-panel" aria-label="Calidad del análisis">
      <h3>Calidad del análisis</h3>
      <p>
        <strong>{POSE_QUALITY_LABEL[analysis.quality_flags.quality] ?? analysis.quality_flags.quality}</strong>
        {" · "}{analysis.quality_flags.visible_landmarks}/{analysis.quality_flags.total_landmarks} landmarks visibles
        {" · poses detectados: "}{analysis.quality_flags.pose_count}
      </p>
      <div className="pose-flags">
        {flags.map((f) => (
          <span key={f} className="pose-flag">{POSE_FLAG_LABEL[f] ?? f}</span>
        ))}
      </div>
      <p className="bv-muted" style={{ fontSize: "0.78rem" }}>
        Umbral de visibilidad {Math.round(analysis.quality_flags.visibility_threshold * 100)}% · modelo{" "}
        <code>{analysis.quality_flags.model_version}</code>
      </p>
    </section>
  );
}

export function PoseAnalysisDetailPage() {
  const { id = "" } = useParams();
  const query = usePoseDetail(id);

  if (query.isLoading) return <p className="bv-muted">Cargando análisis…</p>;
  if (query.error) {
    return (
      <div className="bv-page">
        <p className="bv-alert bv-alert--error">{query.error.message}</p>
        <Link to="/capture" className="bv-muted">← Captura corporal</Link>
      </div>
    );
  }
  if (!query.data) return null;
  const a = query.data;
  const visual = a.status === "completed" || a.status === "needs_review";

  return (
    <div className="bv-page">
      <header className="bv-page__header">
        <div>
          <Link to="/analyses" className="bv-muted">← Análisis de pose</Link>
          <h1>
            Análisis <span className={`bv-tag ${POSE_STATUS_BADGE_CLASS[a.status]}`}>{POSE_STATUS_LABEL[a.status].toUpperCase()}</span>
          </h1>
          <p className="pose-badge" role="note">ESTIMACIÓN VISUAL</p>
        </div>
        <Link to={`/capture/${a.profile_id}`} className="bv-btn bv-btn--small">
          Ver expediente
        </Link>
      </header>

      <p className="bv-alert bv-alert--warn">
        Este resultado es una <strong>estimación visual</strong> generada por IA a partir de una imagen.{" "}
        <strong>No es una medición clínica</strong>, no representa geometría ni diagnósticos, y nunca debe mezclarse con mediciones observadas.
      </p>

      {!visual ? (
        <p className="bv-muted">
          El análisis está {POSE_STATUS_LABEL[a.status].toLowerCase()}. El esquema corporal aparecerá cuando llegue a un estado definitivo.
        </p>
      ) : null}

      {visual ? (
        <div className="pose-detail__grid">
          <div>
            <SkeletonPreview landmarks={a.landmarks} visibilityThreshold={a.quality_flags?.visibility_threshold ?? 0.5} />
          </div>
          <div className="pose-detail__body">
            <QualitySection analysis={a} />
          </div>
        </div>
      ) : null}

      <section className="bv-panel" aria-label="Metadatos del análisis">
        <h3>Metadatos</h3>
        <dl className="pose-detail__kv">
          <dt>Estado</dt><dd>{POSE_STATUS_LABEL[a.status]}</dd>
          <dt>Modelo</dt><dd>{a.model_name ?? "—"} {a.model_version ? <code>({a.model_version})</code> : ""}</dd>
          <dt>Creado por</dt><dd>{a.created_by}</dd>
          <dt>Creado</dt><dd>{formatTimestamp(a.created_at)}</dd>
          <dt>Iniciado</dt><dd>{formatTimestamp(a.started_at)}</dd>
          <dt>Completado</dt><dd>{formatTimestamp(a.completed_at)}</dd>
          <dt>Duración</dt><dd>{formatDurationMs(a.duration_ms)}</dd>
          <dt>Intentos</dt><dd>{a.attempt_count}</dd>
          {a.error_message ? (<><dt>Error</dt><dd style={{ color: "#fca5a5" }}>{a.error_message}</dd></>) : null}
        </dl>
      </section>

      {a.landmarks && a.landmarks.length > 0 ? (
        <section className="bv-panel" aria-label="Landmarks">
          <h3>Landmarks normalizados (ESTIMACIÓN)</h3>
          <p className="bv-muted" style={{ fontSize: "0.78rem" }}>
            Coordenadas del modelo en un espacio [0,1] relativo al fotograma. Solo son referencias visuales.
          </p>
          <div className="pose-landmarks">
            {a.landmarks
              .filter((lm) => (lm.visibility ?? 0) >= (a.quality_flags?.visibility_threshold ?? 0.5))
              .slice(0, 33)
              .map((lm) => (
                <span key={lm.index} className="pose-landmark-chip">
                  {lm.index} · ({lm.x?.toFixed(2) ?? "—"}, {lm.y?.toFixed(2) ?? "—"}) · vis {lm.visibility?.toFixed(2) ?? "—"}
                </span>
              ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

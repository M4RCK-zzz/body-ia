import { Link } from "react-router-dom";
import { useProfileList } from "@/features/profiles/hooks/useProfiles";
import { usePoseFromProfile } from "./hooks/usePose";
import {
  POSE_QUALITY_LABEL,
  POSE_STATUS_BADGE_CLASS,
  POSE_STATUS_LABEL,
  formatTimestamp,
  type PoseAnalysis,
} from "@/types/pose";
import "./pose.css";

function AnalysisRow({ analysis }: { analysis: PoseAnalysis }) {
  return (
    <li className="pose-list__row">
      <div className="pose-list__main">
        <span className={`bv-tag pose-list__status ${POSE_STATUS_BADGE_CLASS[analysis.status]}`}>
          {POSE_STATUS_LABEL[analysis.status].toUpperCase()}
        </span>
        <p className="pose-list__meta">
          {analysis.created_by} · {formatTimestamp(analysis.created_at)}
          {analysis.quality_flags ? ` · ${POSE_QUALITY_LABEL[analysis.quality_flags.quality] ?? analysis.quality_flags.quality}` : ""}
        </p>
      </div>
      <div className="pose-list__actions">
        <Link className="bv-btn bv-btn--small" to={`/analyses/${analysis.id}`}>
          Ver análisis
        </Link>
      </div>
    </li>
  );
}

function ProfileSection({ profileId, displayCode }: { profileId: string; displayCode: string }) {
  const query = usePoseFromProfile(profileId);
  if (query.isLoading) return <p className="bv-muted">Cargando análisis…</p>;
  if (query.error) return <p className="bv-alert bv-alert--error">{query.error.message}</p>;
  const items = query.data?.items ?? [];
  if (items.length === 0) return null;
  return (
    <section className="bv-panel" aria-label={`Análisis de ${displayCode}`}>
      <h2>{displayCode}</h2>
      <ul className="pose-list" style={{ listStyle: "none", padding: 0 }}>
        {items.map((a) => (
          <AnalysisRow key={a.id} analysis={a} />
        ))}
      </ul>
    </section>
  );
}

export function PoseListPage() {
  const profiles = useProfileList();

  return (
    <div className="bv-page">
      <header className="bv-page__header">
        <div>
          <h1>Análisis de pose</h1>
          <span className="pose-badge">ESTIMACIÓN VISUAL</span>
        </div>
        <Link to="/capture" className="bv-btn bv-btn--small">
          Ir a captura
        </Link>
      </header>
      <p className="bv-alert bv-alert--warn">
        Los esquemas corporales generados por IA son <strong>estimaciones visuales</strong>, no mediciones.
      </p>
      {profiles.isLoading ? <p className="bv-muted">Cargando expedientes…</p> : null}
      {profiles.error ? <p className="bv-alert bv-alert--error">{profiles.error.message}</p> : null}
      {profiles.data?.items.map((profile) => (
        <ProfileSection key={profile.id} profileId={profile.id} displayCode={profile.display_code} />
      ))}
      {profiles.data && profiles.data.items.length === 0 ? (
        <p className="bv-muted">No tienes expedientes disponibles.</p>
      ) : null}
    </div>
  );
}

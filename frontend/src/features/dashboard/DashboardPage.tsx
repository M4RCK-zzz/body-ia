import { Link } from "react-router-dom";
import { DataKindBadge } from "@/components/ui/DataKindBadge";
import { formatDateTime } from "@/features/measurements/format";
import { ApiStatusCard } from "./components/ApiStatusCard";
import { DataKindLegend } from "./components/DataKindLegend";
import { MetricCard } from "./components/MetricCard";
import { useDashboardSummary } from "./hooks/useDashboard";

export function DashboardPage() {
  const summary = useDashboardSummary();
  const data = summary.data;

  return (
    <>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p className="muted">
          Indicadores calculados en vivo sobre los expedientes a los que tienes acceso vigente.
          No hay datos agregados de expedientes ajenos.
        </p>
      </div>

      {summary.isLoading ? <p className="muted">Cargando indicadores…</p> : null}
      {summary.error ? (
        <p className="bv-alert bv-alert--error">{summary.error.message}</p>
      ) : null}

      <div className="grid grid--kpi">
        <MetricCard
          label="Expedientes con acceso"
          value={data ? data.profiles_total : null}
          note={
            data
              ? `${data.profiles_active} activo${data.profiles_active === 1 ? "" : "s"}`
              : "Cargando…"
          }
        />
        <MetricCard
          label="Mediciones registradas"
          value={data ? data.measurements_total : null}
          note={
            data
              ? data.profiles_without_measurements > 0
                ? `${data.profiles_without_measurements} expediente(s) sin mediciones`
                : "Todas las métricas vigentes (observadas)"
              : "Cargando…"
          }
        />
        <MetricCard
          label="Análisis de pose"
          value={data ? data.pose_analyses_total : null}
          note="Estimaciones visuales: se cuentan aparte de las mediciones"
        />
      </div>

      <div className="grid grid--two">
        <section className="card">
          <h2 className="card__title">Actividad reciente</h2>
          {data && data.recent_profiles.length === 0 ? (
            <p className="muted">
              Aún no tienes expedientes.{" "}
              <Link to="/expedientes">Crea el primero</Link>.
            </p>
          ) : null}
          {data && data.recent_profiles.length > 0 ? (
            <ul className="dash-profiles">
              {data.recent_profiles.map((profile) => (
                <li key={profile.profile_id} className="dash-profiles__row">
                  <div>
                    <Link to={`/expedientes/${profile.profile_id}`}>{profile.display_code}</Link>
                    <div className="muted dash-profiles__meta">
                      {profile.measurement_count}{" "}
                      {profile.measurement_count === 1 ? "medición" : "mediciones"}
                      {profile.last_measurement_at
                        ? ` · última ${formatDateTime(profile.last_measurement_at)}`
                        : " · sin mediciones"}
                    </div>
                  </div>
                  <div className="dash-profiles__actions">
                    <Link
                      to={`/analytics/${profile.profile_id}`}
                      className="bv-btn bv-btn--small"
                    >
                      Analítica
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
          {data ? (
            <p className="dash-note">
              <DataKindBadge kind="observed" /> {data.note}
            </p>
          ) : null}
        </section>

        <ApiStatusCard />
      </div>

      <div className="grid grid--two">
        <DataKindLegend />
      </div>
    </>
  );
}

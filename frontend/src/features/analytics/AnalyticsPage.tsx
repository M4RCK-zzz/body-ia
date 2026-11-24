import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import "@/components/ui/forms.css";
import { DataKindBadge } from "@/components/ui/DataKindBadge";
import { formatDate } from "@/features/measurements/format";
import { useProfile } from "@/features/profiles/hooks/useProfiles";
import { ReportRequestPanel } from "@/features/reports/ReportRequestPanel";
import { useAnalytics } from "@/features/reports/hooks/useReports";
import { ANALYTICS_WINDOWS, type AnalyticsWindow } from "@/types/analytics";
import { TrendTable } from "./components/TrendTable";
import "./analytics.css";

const WINDOW_LABEL: Record<AnalyticsWindow, string> = {
  7: "7 días",
  30: "30 días",
  90: "90 días",
};

export function AnalyticsPage() {
  const { profileId = "" } = useParams();
  const [windowDays, setWindowDays] = useState<AnalyticsWindow>(30);
  const profile = useProfile(profileId);
  const analytics = useAnalytics(profileId, windowDays);

  if (profile.error) {
    return (
      <div className="bv-page">
        <p className="bv-alert bv-alert--error">{profile.error.message}</p>
        <Link to="/expedientes">← Volver a Expedientes</Link>
      </div>
    );
  }

  return (
    <div className="bv-page">
      <header className="bv-page__header">
        <div>
          <Link to={`/expedientes/${profileId}`} className="bv-muted">
            ← Volver al expediente
          </Link>
          <h1>
            Analítica descriptiva {profile.data ? `· ${profile.data.display_code}` : ""}
          </h1>
          <p className="bv-muted analytics-intro">
            Último valor, cambio absoluto/porcentual, conteo y dispersión de las mediciones
            registradas. <strong>No hay predicciones ni interpretación clínica.</strong>
          </p>
        </div>
        <div className="analytics-windows" role="group" aria-label="Ventana temporal">
          {ANALYTICS_WINDOWS.map((option) => (
            <button
              key={option}
              type="button"
              className="bv-tab"
              aria-pressed={windowDays === option}
              onClick={() => setWindowDays(option)}
            >
              {WINDOW_LABEL[option]}
            </button>
          ))}
        </div>
      </header>

      <p className="bv-alert bv-alert--info">
        <DataKindBadge kind="observed" /> Sólo se agregan mediciones observadas de este expediente.
        Los datos faltantes se listan como ausentes y <strong>nunca se interpolan</strong>.
      </p>

      {analytics.isLoading ? <p className="bv-muted">Calculando estadística descriptiva…</p> : null}

      {analytics.error ? (
        <p className="bv-alert bv-alert--error">{analytics.error.message}</p>
      ) : null}

      {analytics.data ? (
        <>
          <section className="analytics-kpis">
            <div className="analytics-kpi">
              <span className="analytics-kpi__label">Mediciones en ventana</span>
              <span className="analytics-kpi__value">{analytics.data.total_measurements}</span>
              <span className="analytics-kpi__note">
                {formatDate(analytics.data.date_from)} – {formatDate(analytics.data.date_to)}
              </span>
            </div>
            <div className="analytics-kpi">
              <span className="analytics-kpi__label">Métricas con datos</span>
              <span className="analytics-kpi__value">
                {analytics.data.trends.length - analytics.data.metrics_without_data.length}
                <span className="analytics-kpi__suffix">/ {analytics.data.trends.length}</span>
              </span>
              <span className="analytics-kpi__note">El catálogo se informa completo.</span>
            </div>
            <div className="analytics-kpi">
              <span className="analytics-kpi__label">Calculado</span>
              <span className="analytics-kpi__value analytics-kpi__value--small">
                {formatDate(analytics.data.computed_at)}
              </span>
              <span className="analytics-kpi__note">Estadística descriptiva, sin proyección.</span>
            </div>
          </section>

          {analytics.data.metrics_without_data.length > 0 ? (
            <p className="bv-alert bv-alert--warn">
              <strong>Sin datos en la ventana:</strong>{" "}
              {analytics.data.metrics_without_data.join(", ")}. No se rellenan ni se estiman.
            </p>
          ) : null}

          <section className="bv-panel">
            <h2>Resumen por métrica</h2>
            <TrendTable trends={analytics.data.trends} />
          </section>

          <p className="analytics-disclaimer">{analytics.data.disclaimer}</p>
        </>
      ) : null}

      <ReportRequestPanel profileId={profileId} />
    </div>
  );
}

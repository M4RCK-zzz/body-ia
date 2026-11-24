import { useState } from "react";
import type { Measurement, MeasurementCatalog, MeasurementType } from "@/types/measurement";
import { CorrectionForm } from "./components/CorrectionForm";
import { HistoryPanel } from "./components/HistoryPanel";
import { MeasurementForm } from "./components/MeasurementForm";
import { MeasurementTable } from "./components/MeasurementTable";
import { MetricChart } from "./components/MetricChart";
import { useMeasurementList, useMeasurementSeries } from "./hooks/useMeasurements";

interface Props {
  profileId: string;
  catalog: MeasurementCatalog;
  readOnly: boolean;
  readOnlyReason?: string;
}

export function MeasurementsWorkspace({ profileId, catalog, readOnly, readOnlyReason }: Props) {
  const [metric, setMetric] = useState<MeasurementType>(catalog.metrics[0].metric_type);
  const [showReplaced, setShowReplaced] = useState(false);
  const [correcting, setCorrecting] = useState<Measurement | null>(null);
  const [historyOf, setHistoryOf] = useState<Measurement | null>(null);

  const spec = catalog.metrics.find((m) => m.metric_type === metric) ?? catalog.metrics[0];
  const list = useMeasurementList(profileId, metric, showReplaced);
  const series = useMeasurementSeries(profileId, metric);

  function selectMetric(next: MeasurementType) {
    setMetric(next);
    setCorrecting(null);
    setHistoryOf(null);
  }

  return (
    <>
      <section className="bv-panel">
        <h2>
          Historial real <span className="bv-tag bv-tag--observed">MEDICIÓN OBSERVADA</span>
        </h2>
        <p className="bv-muted">
          Todo lo que ves en esta sección son mediciones registradas por personas. Las simulaciones
          y escenarios hipotéticos (Fase 8) <strong>nunca</strong> se mezclan con estos datos ni con
          estos gráficos.
        </p>
        <div className="bv-tabs" role="group" aria-label="Métrica">
          {catalog.metrics.map((m) => (
            <button
              key={m.metric_type}
              type="button"
              className="bv-tab"
              aria-pressed={m.metric_type === metric}
              onClick={() => selectMetric(m.metric_type)}
            >
              {m.label}
            </button>
          ))}
        </div>
      </section>

      {readOnly ? (
        <p className="bv-alert bv-alert--warn">
          {readOnlyReason ?? "Historial de solo lectura."}
        </p>
      ) : (
        <section className="bv-panel">
          <MeasurementForm key={metric} profileId={profileId} spec={spec} catalog={catalog} />
        </section>
      )}

      <section className="bv-panel">
        <h2>Evolución temporal: {spec.label}</h2>
        {series.isLoading ? <p className="bv-muted">Cargando gráfico…</p> : null}
        {series.error ? <p className="bv-alert bv-alert--error">{series.error.message}</p> : null}
        {series.data ? <MetricChart series={series.data} spec={spec} catalog={catalog} /> : null}
      </section>

      <section className="bv-panel">
        <h2>Registros de {spec.label.toLowerCase()}</h2>
        <label
          className="bv-muted bv-check bv-check--inline"
        >
          <input
            type="checkbox"
            checked={showReplaced}
            onChange={(e) => setShowReplaced(e.target.checked)}
          />
          Mostrar también versiones reemplazadas
        </label>
        {list.isLoading ? <p className="bv-muted">Cargando…</p> : null}
        {list.error ? <p className="bv-alert bv-alert--error">{list.error.message}</p> : null}
        {list.data ? (
          <MeasurementTable
            rows={list.data.items}
            catalog={catalog}
            readOnly={readOnly}
            onCorrect={(m) => {
              setHistoryOf(null);
              setCorrecting(m);
            }}
            onHistory={(m) => {
              setCorrecting(null);
              setHistoryOf(m);
            }}
          />
        ) : null}
      </section>

      {correcting ? (
        <CorrectionForm
          key={correcting.id}
          profileId={profileId}
          original={correcting}
          spec={spec}
          catalog={catalog}
          onClose={() => setCorrecting(null)}
        />
      ) : null}
      {historyOf ? (
        <HistoryPanel
          key={historyOf.id}
          profileId={profileId}
          measurement={historyOf}
          catalog={catalog}
          onClose={() => setHistoryOf(null)}
        />
      ) : null}
    </>
  );
}

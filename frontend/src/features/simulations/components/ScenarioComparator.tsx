import { DataKindBadge } from "@/components/ui/DataKindBadge";
import { formatDateTime } from "@/features/measurements/format";
import { metricLabel, type MetricLabelMap } from "@/features/measurements/metricLabels";
import { DERIVED_LABEL, type SimulationComparison } from "@/types/simulation";

const nf = new Intl.NumberFormat("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const num = (value: number | string | null) =>
  value === null || value === "" ? "—" : nf.format(Number(value));

const signed = (value: number | string | null) => {
  if (value === null || value === "") return "—";
  const numeric = Number(value);
  return `${numeric > 0 ? "+" : ""}${nf.format(numeric)}`;
};

/**
 * Etiqueta de una métrica del comparador.
 *
 * Las claves derivadas (`waist_height`, `waist_hip`) tienen su propio diccionario;
 * el resto son métricas del catálogo (`waist`, `hip`, …) y se traducen con el mapa
 * compartido, sin inventar nombres.
 */
const label = (metric: string, labels?: MetricLabelMap) =>
  DERIVED_LABEL[metric] ??
  metricLabel(metric, labels);

/**
 * Comparador base observada vs escenario. Dos columnas claramente etiquetadas,
 * sin líneas temporales ni extrapolación: no hay "proyección" que leer.
 */
export function ScenarioComparator({
  comparison,
  metricLabels,
}: {
  comparison: SimulationComparison;
  metricLabels?: MetricLabelMap;
}) {
  const baselineByMetric = new Map(
    comparison.baseline.metrics.map((metric) => [metric.metric_type, metric]),
  );
  const clamped = comparison.scenario.metrics.filter((metric) => metric.clamped);

  return (
    <section className="bv-panel scenario-comparator">
      <h2>Comparador base vs escenario</h2>
      <p className="bv-muted">
        {comparison.label} · motor <code>{comparison.engine.name} {comparison.engine.version}</code>{" "}
        · {formatDateTime(comparison.created_at)} · por {comparison.created_by}
      </p>

      <div className="table-wrap">
        <table className="bv-table scenario-table">
          <caption className="scenario-table__caption">
            Valores observados registrados frente al resultado hipotético del escenario.
          </caption>
          <thead>
            <tr>
              <th scope="col">Métrica</th>
              <th scope="col">
                <span className="scenario-table__head">
                  <DataKindBadge kind="observed" /> Base observada
                </span>
              </th>
              <th scope="col">
                <span className="scenario-table__head">
                  <DataKindBadge kind="simulation" /> Escenario
                </span>
              </th>
              <th scope="col">Δ absoluto</th>
              <th scope="col">Δ %</th>
            </tr>
          </thead>
          <tbody>
            {comparison.scenario.metrics.map((metric) => {
              const base = baselineByMetric.get(metric.metric_type);
              return (
                <tr key={metric.metric_type}>
                  <th scope="row">{label(metric.metric_type, metricLabels)}</th>
                  <td>{base ? `${num(base.value)} ${base.unit}` : "—"}</td>
                  <td className="scenario-table__value">
                    {num(metric.value)} {metric.unit}
                    {metric.clamped ? (
                      <span className="scenario-clamped" title="Acotado al rango técnico del catálogo">
                        acotado
                      </span>
                    ) : null}
                  </td>
                  <td className="delta-abs">
                    {signed(metric.delta_absolute)} {metric.unit}
                  </td>
                  <td>{metric.delta_percent === null ? "—" : `${signed(metric.delta_percent)} %`}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {Object.keys(comparison.derived).length > 0 ? (
        <div className="scenario-derived">
          <h3>Indicadores aritméticos del escenario</h3>
          <p className="bv-muted">
            Divisiones entre valores de la misma base. Sin valores de referencia ni semáforos.
          </p>
          <ul>
            {Object.entries(comparison.derived).map(([key, value]) => (
              <li key={key}>
                <strong>{DERIVED_LABEL[key] ?? key}</strong>{" "}
                <code>{value.components}</code>: {num(value.baseline)} → {num(value.simulated)}
                {value.delta_absolute === null ? "" : ` (${signed(value.delta_absolute)})`}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {comparison.unchanged.length > 0 ? (
        <p className="scenario-unchanged">
          <strong>Sin cambios en este escenario:</strong>{" "}
          {comparison.unchanged.map((metric) => label(metric, metricLabels)).join(", ")}.
        </p>
      ) : null}

      {clamped.length > 0 ? (
        <p className="bv-alert bv-alert--warn">
          El resultado de {clamped.map((metric) => label(metric.metric_type, metricLabels)).join(", ")} se acotó
          al rango técnico del catálogo: el valor pedido quedaba fuera de rango.
        </p>
      ) : null}

      {comparison.baseline.metrics.some((metric) => metric.superseded_since) ? (
        <p className="bv-alert bv-alert--info">
          La base de este escenario fue corregida después de calcularlo. Se muestra la copia usada
          ese día: el escenario no se recalcula ni se reescribe.
        </p>
      ) : null}

      <dl className="scenario-trace">
        <dt>Checksum del resultado (SHA-256)</dt>
        <dd>
          <code>{comparison.result_checksum ?? "—"}</code>
        </dd>
        <dt>Hash de la base</dt>
        <dd>
          <code>{comparison.baseline_hash}</code>
        </dd>
      </dl>

      <p className="scenario-disclaimer">{comparison.disclaimer}</p>
    </section>
  );
}

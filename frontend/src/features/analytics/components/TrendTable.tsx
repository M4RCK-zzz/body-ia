import { DataKindBadge } from "@/components/ui/DataKindBadge";
import type { MetricTrend } from "@/types/analytics";
import { formatDateTime } from "@/features/measurements/format";
import { deltaDirection, signed, signedPercent, valueOrDash } from "../format";

/**
 * Tabla descriptiva por métrica. Sin gráficos de tendencia futura: cada columna
 * es un dato ya medido. Las métricas sin datos muestran "—", nunca 0.00.
 */
export function TrendTable({ trends }: { trends: MetricTrend[] }) {
  return (
    <div className="table-wrap">
      <table className="bv-table analytics-table">
        <caption className="analytics-table__caption">
          Último valor, cambio respecto al anterior y dispersión. Sin proyecciones.
        </caption>
        <thead>
          <tr>
            <th scope="col">Métrica</th>
            <th scope="col">n</th>
            <th scope="col">Último</th>
            <th scope="col">Δ abs.</th>
            <th scope="col">Δ %</th>
            <th scope="col">Mín / Máx</th>
            <th scope="col">Mediana</th>
            <th scope="col">Atípicos</th>
            <th scope="col">Última toma</th>
          </tr>
        </thead>
        <tbody>
          {trends.map((trend) => {
            const direction = deltaDirection(trend.delta_absolute);
            const hasData = trend.count > 0;
            return (
              <tr key={trend.metric_type} className={hasData ? undefined : "is-empty"}>
                <th scope="row" className="analytics-table__metric">
                  <span>{trend.label}</span>
                  <span className="analytics-table__unit">{trend.unit}</span>
                  {trend.corrected_count > 0 ? (
                    <span className="analytics-table__note">
                      {trend.corrected_count} corregida{trend.corrected_count === 1 ? "" : "s"}
                    </span>
                  ) : null}
                </th>
                <td>{trend.count}</td>
                <td className="analytics-table__value">{valueOrDash(trend.last_value, trend.unit)}</td>
                <td className={`delta delta--${direction}`}>{signed(trend.delta_absolute, trend.unit)}</td>
                <td className={`delta delta--${direction}`}>{signedPercent(trend.delta_percent)}</td>
                <td className="analytics-table__range">
                  {valueOrDash(trend.min_value)} / {valueOrDash(trend.max_value)}
                </td>
                <td>{valueOrDash(trend.median_value)}</td>
                <td>
                  {trend.outlier_count === 0 ? (
                    <span className="bv-muted">—</span>
                  ) : (
                    <span className="analytics-outlier" title="Marcado por mediana ± 3.5·MAD">
                      {trend.outlier_count} marcado{trend.outlier_count === 1 ? "" : "s"}
                    </span>
                  )}
                </td>
                <td className="analytics-table__when">
                  {trend.last_at ? formatDateTime(trend.last_at) : <span className="bv-muted">sin datos</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="analytics-footnote">
        <DataKindBadge kind="observed" /> Sólo mediciones registradas. Los valores faltantes se
        muestran como “—” y <strong>no se interpolan ni se estiman</strong>.
      </p>
    </div>
  );
}

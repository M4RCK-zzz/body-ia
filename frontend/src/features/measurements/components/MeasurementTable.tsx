import type { Measurement, MeasurementCatalog } from "@/types/measurement";
import { formatDateTime, formatValue, methodLabel } from "../format";

interface Props {
  rows: Measurement[];
  catalog: MeasurementCatalog;
  readOnly: boolean;
  onCorrect: (m: Measurement) => void;
  onHistory: (m: Measurement) => void;
}

function stateLabel(m: Measurement): string {
  if (!m.is_current) return "Reemplazada";
  return m.supersedes_id ? "Corrección vigente" : "Original";
}

export function MeasurementTable({ rows, catalog, readOnly, onCorrect, onHistory }: Props) {
  if (rows.length === 0) {
    return <p className="bv-muted">Aún no hay mediciones de esta métrica.</p>;
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table className="bv-table">
        <thead>
          <tr>
            <th>Fecha de medición</th>
            <th>Valor</th>
            <th>Método</th>
            <th>Registrado por</th>
            <th>Estado</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((m) => (
            <tr key={m.id} className={m.is_current ? undefined : "is-replaced"}>
              <td>{formatDateTime(m.measured_at)}</td>
              <td>{formatValue(m.value, m.unit)}</td>
              <td>{methodLabel(catalog, m.method)}</td>
              <td>{m.created_by}</td>
              <td className="no-strike">
                {stateLabel(m)}
                {m.correction_reason ? <div className="bv-muted">{m.correction_reason}</div> : null}
              </td>
              <td className="no-strike">
                <div className="bv-actions">
                  {m.is_current && !readOnly ? (
                    <button
                      type="button"
                      className="bv-btn bv-btn--small"
                      onClick={() => onCorrect(m)}
                    >
                      Corregir
                    </button>
                  ) : null}
                  {m.supersedes_id || !m.is_current ? (
                    <button
                      type="button"
                      className="bv-btn bv-btn--small"
                      onClick={() => onHistory(m)}
                    >
                      Versiones
                    </button>
                  ) : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

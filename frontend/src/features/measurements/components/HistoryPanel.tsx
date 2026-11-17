import type { Measurement, MeasurementCatalog } from "@/types/measurement";
import { formatDateTime, formatValue, methodLabel } from "../format";
import { useMeasurementHistory } from "../hooks/useMeasurements";

interface Props {
  profileId: string;
  measurement: Measurement;
  catalog: MeasurementCatalog;
  onClose: () => void;
}

export function HistoryPanel({ profileId, measurement, catalog, onClose }: Props) {
  const { data, isLoading, error } = useMeasurementHistory(profileId, measurement.id);

  return (
    <section className="bv-panel" aria-label="Historial de versiones">
      <h3>Versiones de esta medición</h3>
      {isLoading ? <p className="bv-muted">Cargando…</p> : null}
      {error ? <p className="bv-alert bv-alert--error">{error.message}</p> : null}
      <ol>
        {data?.map((version, index) => (
          <li key={version.id} style={{ marginBottom: "0.6rem" }}>
            <strong>v{index + 1}</strong> · {formatValue(version.value, version.unit)} ·{" "}
            {methodLabel(catalog, version.method)} · medido el {formatDateTime(version.measured_at)}
            {version.is_current ? <span className="bv-tag bv-tag--status" style={{ marginLeft: 8 }}>VIGENTE</span> : null}
            <div className="bv-muted">
              Registrado por {version.created_by} el {formatDateTime(version.recorded_at)}
              {version.correction_reason ? ` · Motivo: ${version.correction_reason}` : ""}
            </div>
          </li>
        ))}
      </ol>
      <button type="button" className="bv-btn" onClick={onClose}>Cerrar</button>
    </section>
  );
}
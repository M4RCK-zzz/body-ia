import { useMemo, useState } from "react";
import type {
  ParameterMode,
  SimulationCreatePayload,
  SimulationLimits,
  SimulationMetricParameter,
} from "@/types/simulation";
import { PARAMETER_MODE_LABEL } from "@/types/simulation";

interface Row {
  metric_type: string;
  mode: ParameterMode;
  value: string;
}

interface Props {
  limits: SimulationLimits;
  disabled: boolean;
  disabledReason?: string;
  submitting: boolean;
  onSubmit: (payload: SimulationCreatePayload) => void;
}

const DEFAULT_ROW: Row = { metric_type: "waist", mode: "delta_absolute", value: "" };

export function ScenarioForm({ limits, disabled, disabledReason, submitting, onSubmit }: Props) {
  const [label, setLabel] = useState("Escenario A");
  const [notes, setNotes] = useState("");
  const [rows, setRows] = useState<Row[]>([{ ...DEFAULT_ROW }]);

  const metricMap = useMemo(
    () => new Map(limits.metrics.map((metric) => [metric.metric_type as string, metric])),
    [limits],
  );

  const rowsWithSpec = rows.map((row) => ({ ...row, spec: metricMap.get(row.metric_type) }));
  const validRows = rowsWithSpec.filter((row) => row.spec && row.value.trim() !== "");
  const canSubmit =
    !disabled && !submitting && label.trim().length > 0 && validRows.length > 0 && validRows.length <= 4;

  const update = (index: number, patch: Partial<Row>) =>
    setRows((current) => current.map((row, position) => (position === index ? { ...row, ...patch } : row)));

  const submit = () => {
    if (!canSubmit) return;
    const metrics: SimulationMetricParameter[] = validRows.map((row) => ({
      metric_type: row.metric_type,
      mode: row.mode,
      value: Number(row.value),
    }));
    onSubmit({
      label: label.trim(),
      notes: notes.trim() ? notes.trim() : null,
      run_now: true,
      metrics,
    });
  };

  return (
    <section className="bv-panel scenario-form">
      <h2>Nuevo escenario</h2>
      <p className="bv-muted">
        Define entre 1 y 4 cambios. El tope es del{" "}
        <strong>{limits.max_delta_percent}%</strong> por métrica y el resultado se acota siempre al
        rango técnico del catálogo.
      </p>

      <div className="bv-row">
        <div className="bv-field">
          <label htmlFor="scenario-label">Nombre del escenario</label>
          <input
            id="scenario-label"
            className="bv-input"
            value={label}
            maxLength={80}
            onChange={(event) => setLabel(event.target.value)}
          />
        </div>
        <div className="bv-field">
          <label htmlFor="scenario-notes">Nota (opcional)</label>
          <input
            id="scenario-notes"
            className="bv-input"
            value={notes}
            maxLength={500}
            placeholder="Qué quieres explorar con este escenario"
            onChange={(event) => setNotes(event.target.value)}
          />
        </div>
      </div>

      <div className="scenario-rows">
        {rows.map((row, index) => {
          const spec = metricMap.get(row.metric_type);
          const hint =
            row.mode === "delta_percent"
              ? `±${limits.max_delta_percent} %`
              : row.mode === "delta_absolute"
                ? `Máximo ±${limits.max_delta_percent} % del valor medido`
                : spec
                  ? `Entre ${spec.min_value} y ${spec.max_value} ${spec.unit}`
                  : "";
          return (
            <div className="scenario-row" key={index}>
              <div className="bv-field">
                <label htmlFor={`metric-${index}`}>Métrica</label>
                <select
                  id={`metric-${index}`}
                  className="bv-input"
                  value={row.metric_type}
                  onChange={(event) => update(index, { metric_type: event.target.value })}
                >
                  {limits.metrics.map((metric) => (
                    <option key={metric.metric_type} value={metric.metric_type}>
                      {metric.label} ({metric.unit})
                    </option>
                  ))}
                </select>
              </div>
              <div className="bv-field">
                <label htmlFor={`mode-${index}`}>Tipo de cambio</label>
                <select
                  id={`mode-${index}`}
                  className="bv-input"
                  value={row.mode}
                  onChange={(event) => update(index, { mode: event.target.value as ParameterMode })}
                >
                  {limits.modes.map((mode) => (
                    <option key={mode} value={mode}>
                      {PARAMETER_MODE_LABEL[mode]}
                    </option>
                  ))}
                </select>
              </div>
              <div className="bv-field scenario-row__value">
                <label htmlFor={`value-${index}`}>
                  Valor {row.mode === "delta_percent" ? "(%)" : spec ? `(${spec.unit})` : ""}
                </label>
                <input
                  id={`value-${index}`}
                  className="bv-input"
                  inputMode="decimal"
                  value={row.value}
                  placeholder="0.00"
                  onChange={(event) => update(index, { value: event.target.value })}
                />
                <span className="bv-field__hint">{hint}</span>
              </div>
              <button
                type="button"
                className="bv-btn bv-btn--small scenario-row__remove"
                onClick={() => setRows((current) => current.filter((_, position) => position !== index))}
                disabled={rows.length === 1}
                aria-label={`Quitar cambio ${index + 1}`}
              >
                Quitar
              </button>
            </div>
          );
        })}
      </div>

      <div className="bv-row">
        <button
          type="button"
          className="bv-btn bv-btn--small"
          onClick={() => setRows((current) => [...current, { ...DEFAULT_ROW }])}
          disabled={rows.length >= 4}
        >
          Añadir métrica
        </button>
        <button
          type="button"
          className="bv-btn bv-btn--primary"
          onClick={submit}
          disabled={!canSubmit}
        >
          {submitting ? "Enviando…" : "Calcular escenario"}
        </button>
        <span className="bv-muted">
          La estatura no se simula: solo se usa como referencia de los indicadores derivados.
        </span>
      </div>

      {disabled && disabledReason ? (
        <p className="bv-alert bv-alert--warn">{disabledReason}</p>
      ) : null}
    </section>
  );
}

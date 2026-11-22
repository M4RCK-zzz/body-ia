import { useState, type FormEvent } from "react";
import { FormField } from "@/components/ui/FormField";
import type { Measurement, MeasurementCatalog, MeasurementMethod, MetricSpec } from "@/types/measurement";
import { formatValue, toLocalInputValue } from "../format";
import { useCorrectMeasurement } from "../hooks/useMeasurements";
import { parseDecimal, validateInput, type InputErrors } from "../validation";

interface Props {
  profileId: string;
  original: Measurement;
  spec: MetricSpec;
  catalog: MeasurementCatalog;
  onClose: () => void;
}

export function CorrectionForm({ profileId, original, spec, catalog, onClose }: Props) {
  const [value, setValue] = useState(String(original.value));
  const [measuredAt, setMeasuredAt] = useState(() => toLocalInputValue(new Date(original.measured_at)));
  const [method, setMethod] = useState<MeasurementMethod>(original.method);
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<InputErrors>({});
  const mutation = useCorrectMeasurement(profileId);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validateInput({ value, measuredAt, reason }, spec);
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    mutation.mutate(
      {
        measurementId: original.id,
        payload: {
          value: parseDecimal(value),
          measured_at: new Date(measuredAt).toISOString(),
          method,
          reason: reason.trim(),
        },
      },
      { onSuccess: onClose },
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="bv-panel" aria-label="Corregir medición">
      <h3>Corregir medición ({formatValue(original.value, original.unit)})</h3>
      <p className="bv-alert bv-alert--info">
        El valor original <strong>no se borra ni se sobrescribe</strong>: se crea una nueva versión
        a tu nombre con el motivo, y la anterior queda en el historial.
      </p>
      <div className="bv-row" style={{ marginTop: "0.75rem" }}>
        <FormField label={`Nuevo valor (${spec.unit})`} htmlFor="c-value" error={errors.value}>
          <input
            id="c-value"
            className="bv-input"
            inputMode="decimal"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </FormField>
        <FormField label="Fecha y hora" htmlFor="c-date" error={errors.measuredAt}>
          <input
            id="c-date"
            type="datetime-local"
            className="bv-input"
            value={measuredAt}
            max={toLocalInputValue(new Date())}
            onChange={(e) => setMeasuredAt(e.target.value)}
          />
        </FormField>
        <FormField label="Método" htmlFor="c-method">
          <select
            id="c-method"
            className="bv-input"
            value={method}
            onChange={(e) => setMethod(e.target.value as MeasurementMethod)}
          >
            {catalog.methods.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </FormField>
      </div>
      <div className="bv-row" style={{ marginTop: "0.75rem" }}>
        <FormField label="Motivo de la corrección" htmlFor="c-reason" error={errors.reason}>
          <input
            id="c-reason"
            className="bv-input"
            value={reason}
            maxLength={300}
            onChange={(e) => setReason(e.target.value)}
          />
        </FormField>
      </div>
      <div className="bv-actions" style={{ marginTop: "0.75rem" }}>
        <button type="submit" className="bv-btn bv-btn--primary" disabled={mutation.isPending}>
          {mutation.isPending ? "Guardando…" : "Guardar corrección"}
        </button>
        <button type="button" className="bv-btn" onClick={onClose}>
          Cancelar
        </button>
      </div>
      {mutation.isError ? (
        <p className="bv-alert bv-alert--error" role="alert">
          {mutation.error.message}
        </p>
      ) : null}
    </form>
  );
}

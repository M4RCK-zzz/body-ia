import { useState, type FormEvent } from "react";
import { FormField } from "@/components/ui/FormField";
import type { MeasurementCatalog, MeasurementMethod, MetricSpec } from "@/types/measurement";
import { toLocalInputValue } from "../format";
import { useRecordMeasurement } from "../hooks/useMeasurements";
import { parseDecimal, validateInput, type InputErrors } from "../validation";

interface Props {
  profileId: string;
  spec: MetricSpec;
  catalog: MeasurementCatalog;
}

export function MeasurementForm({ profileId, spec, catalog }: Props) {
  const [value, setValue] = useState("");
  const [measuredAt, setMeasuredAt] = useState(() => toLocalInputValue(new Date()));
  const [method, setMethod] = useState<MeasurementMethod>("manual_tape");
  const [notes, setNotes] = useState("");
  const [errors, setErrors] = useState<InputErrors>({});
  const mutation = useRecordMeasurement(profileId);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validateInput({ value, measuredAt }, spec);
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    mutation.mutate(
      {
        metric_type: spec.metric_type,
        value: parseDecimal(value),
        unit: spec.unit,
        measured_at: new Date(measuredAt).toISOString(),
        method,
        notes: notes.trim() || null,
      },
      {
        onSuccess: () => {
          setValue("");
          setNotes("");
          setMeasuredAt(toLocalInputValue(new Date()));
        },
      },
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <h3>
        Registrar medición: {spec.label} ({spec.unit})
      </h3>
      <div className="bv-row">
        <FormField
          label={`Valor (${spec.unit})`}
          htmlFor="m-value"
          error={errors.value}
          hint={`Rango técnico: ${spec.min_value}–${spec.max_value}`}
        >
          <input
            id="m-value"
            className="bv-input"
            inputMode="decimal"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </FormField>
        <FormField label="Fecha y hora de la medición" htmlFor="m-date" error={errors.measuredAt}>
          <input
            id="m-date"
            type="datetime-local"
            className="bv-input"
            value={measuredAt}
            max={toLocalInputValue(new Date())}
            onChange={(e) => setMeasuredAt(e.target.value)}
          />
        </FormField>
        <FormField label="Método" htmlFor="m-method">
          <select
            id="m-method"
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
      <p className="bv-muted" style={{ marginTop: "0.5rem" }}>
        Se registrará a tu nombre y quedará en el historial.
      </p>
      <div className="bv-row" style={{ marginTop: "0.75rem" }}>
        <FormField label="Notas (opcional)" htmlFor="m-notes">
          <input
            id="m-notes"
            className="bv-input"
            value={notes}
            maxLength={500}
            onChange={(e) => setNotes(e.target.value)}
          />
        </FormField>
        <button type="submit" className="bv-btn bv-btn--primary" disabled={mutation.isPending}>
          {mutation.isPending ? "Guardando…" : "Guardar medición"}
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

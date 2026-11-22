import type { MetricSpec } from "@/types/measurement";

export interface RawInput {
  value: string;
  measuredAt: string;
  reason?: string;
}

export type InputErrors = Partial<Record<"value" | "measuredAt" | "reason", string>>;

export const parseDecimal = (raw: string) => Number(raw.trim().replace(",", "."));

export function validateInput(raw: RawInput, spec: MetricSpec, now = new Date()): InputErrors {
  const errors: InputErrors = {};
  const value = parseDecimal(raw.value);

  if (raw.value.trim() === "" || !Number.isFinite(value)) {
    errors.value = "Ingresa un número válido.";
  } else if (Math.abs(value * 100 - Math.round(value * 100)) > 1e-6) {
    errors.value = "Máximo 2 decimales.";
  } else if (value < spec.min_value || value > spec.max_value) {
    errors.value = `Debe estar entre ${spec.min_value} y ${spec.max_value} ${spec.unit} (rango técnico).`;
  }

  const date = new Date(raw.measuredAt);
  if (raw.measuredAt === "" || Number.isNaN(date.getTime())) {
    errors.measuredAt = "Indica la fecha y hora de la medición.";
  } else if (date.getTime() > now.getTime() + 5 * 60_000) {
    errors.measuredAt = "La fecha no puede estar en el futuro.";
  }

  if (raw.reason !== undefined) {
    const reason = raw.reason.trim();
    if (reason.length < 3 || reason.length > 300) {
      errors.reason = "Explica el motivo (3 a 300 caracteres).";
    }
  }

  return errors;
}

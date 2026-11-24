import type { MeasurementUnit } from "@/types/measurement";

const nf = new Intl.NumberFormat("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Un valor ausente NUNCA se muestra como 0.00: se muestra como raya. */
export function valueOrDash(value: number | null, unit?: MeasurementUnit): string {
  if (value === null || value === undefined) return "—";
  const text = nf.format(value);
  return unit ? `${text} ${unit}` : text;
}

export function signed(value: number | null, unit?: MeasurementUnit): string {
  if (value === null || value === undefined) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${valueOrDash(value, unit)}`;
}

export function signedPercent(value: number | null): string {
  if (value === null || value === undefined) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${nf.format(value)} %`;
}

/** Dirección del cambio, para colorear sin implicar interpretación clínica. */
export function deltaDirection(value: number | null): "up" | "down" | "flat" {
  if (value === null || value === undefined || value === 0) return "flat";
  return value > 0 ? "up" : "down";
}

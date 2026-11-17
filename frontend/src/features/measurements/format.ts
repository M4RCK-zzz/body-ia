import type { MeasurementCatalog, MeasurementMethod, MeasurementUnit } from "@/types/measurement";

const dateTime = new Intl.DateTimeFormat("es-PE", { dateStyle: "medium", timeStyle: "short" });
const dateOnly = new Intl.DateTimeFormat("es-PE", { dateStyle: "medium" });

export const formatDateTime = (iso: string | number) => dateTime.format(new Date(iso));
export const formatDate = (iso: string | number) => dateOnly.format(new Date(iso));
export const formatValue = (value: number, unit: MeasurementUnit) => `${value.toFixed(2)} ${unit}`;

export function methodLabel(catalog: MeasurementCatalog, method: MeasurementMethod): string {
  return catalog.methods.find((m) => m.value === method)?.label ?? method;
}

export function toLocalInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}
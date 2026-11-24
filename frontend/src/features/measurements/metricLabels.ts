import type { MeasurementType } from "@/types/measurement";

/**
 * Etiquetas de métricas en español para cualquier superficie que reciba la clave
 * cruda del backend (`weight`, `waist`, …).
 *
 * Fuente de verdad: el catálogo de `GET /api/catalog/measurements`
 * (`MetricSpec.label`), que es el que usa el formulario de mediciones. Esta copia
 * solo existe para los sitios que pintan `metric_type` **sin** tener el catálogo
 * cargado (lista de escenarios, parámetros de una simulación): así nunca se ve el
 * identificador en inglés y la etiqueta coincide con el resto de la app.
 *
 * `METRIC_LABELS_FALLBACK` es deliberadamente el mismo texto que devuelve el
 * catálogo; si el catálogo cambia, el helper acepta `labels` para sobreescribirlo.
 */
export const METRIC_LABELS_FALLBACK: Record<MeasurementType, string> = {
  weight: "Peso",
  height: "Estatura",
  waist: "Cintura",
  hip: "Cadera",
  chest: "Pecho",
  arm: "Brazo",
  thigh: "Muslo",
};

export type MetricLabelMap = Partial<Record<string, string>>;

/** `waist` → `Cintura`. Una clave desconocida se devuelve tal cual (nunca se oculta). */
export function metricLabel(metricType: string, labels?: MetricLabelMap): string {
  return labels?.[metricType] ?? METRIC_LABELS_FALLBACK[metricType as MeasurementType] ?? metricType;
}

/** Convierte `MetricSpec[]` del catálogo en el mapa que consume `metricLabel`. */
export function labelsFromCatalog(
  metrics: { metric_type: string; label: string }[] | undefined,
): MetricLabelMap | undefined {
  if (!metrics || metrics.length === 0) return undefined;
  return Object.fromEntries(metrics.map((metric) => [metric.metric_type, metric.label]));
}

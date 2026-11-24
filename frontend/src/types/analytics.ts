import type { DataKind } from "./dataKind";
import type { MeasurementType, MeasurementUnit } from "./measurement";

/** Ventanas admitidas por la API (días). No se aceptan otras. */
export type AnalyticsWindow = 7 | 30 | 90;
export const ANALYTICS_WINDOWS: AnalyticsWindow[] = [7, 30, 90];

/**
 * Estadística **descriptiva** de una métrica. Nunca hay proyecciones: si no hay
 * datos, `count` es 0 y todos los valores son `null` (nunca 0).
 */
export interface MetricTrend {
  metric_type: MeasurementType;
  label: string;
  unit: MeasurementUnit;
  count: number;
  corrected_count: number;
  first_at: string | null;
  last_at: string | null;
  last_value: number | null;
  previous_value: number | null;
  delta_absolute: number | null;
  delta_percent: number | null;
  min_value: number | null;
  max_value: number | null;
  mean_value: number | null;
  median_value: number | null;
  outlier_count: number;
  outlier_timestamps: string[];
}

export interface AnalyticsSummary {
  profile_id: string;
  window_days: number;
  date_from: string;
  date_to: string;
  data_kind: "observed";
  computed_at: string;
  total_measurements: number;
  metrics_without_data: string[];
  trends: MetricTrend[];
  disclaimer: string;
}

export interface DashboardProfile {
  profile_id: string;
  display_code: string;
  status: string;
  my_access: string;
  measurement_count: number;
  last_measurement_at: string | null;
}

export interface DashboardSummary {
  data_kind: DataKind;
  computed_at: string;
  profiles_total: number;
  profiles_active: number;
  measurements_total: number;
  profiles_without_measurements: number;
  pose_analyses_total: number;
  pose_by_status: Record<string, number>;
  recent_profiles: DashboardProfile[];
  note: string;
}

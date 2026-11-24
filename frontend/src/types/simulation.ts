import type { DataKind } from "./dataKind";
import type { MeasurementType, MeasurementUnit } from "./measurement";

export type SimulationStatus = "draft" | "queued" | "completed" | "failed" | "archived";
export type ParameterMode = "delta_absolute" | "delta_percent" | "target_value";

export interface SimulationMetricParameter {
  metric_type: string;
  mode: ParameterMode;
  value: number;
}

export interface Simulation {
  id: string;
  profile_id: string;
  label: string;
  status: SimulationStatus;
  data_kind: "simulation";
  engine_name: string;
  engine_version: string;
  parameters_json: { metrics: { metric_type: string; mode: ParameterMode; value: string }[] };
  baseline_hash: string;
  result_json: Record<string, unknown> | null;
  result_checksum: string | null;
  notes: string | null;
  error_message: string | null;
  created_by: string;
  created_at: string;
  queued_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  archived_at: string | null;
  duration_ms: number | null;
  disclaimer: string;
}

export interface SimulationCreatePayload {
  label: string;
  notes?: string | null;
  run_now: boolean;
  metrics: SimulationMetricParameter[];
}

export interface SimulationLimits {
  engine: { name: string; version: string };
  modes: ParameterMode[];
  max_delta_percent: number;
  metrics: {
    metric_type: MeasurementType;
    label: string;
    unit: MeasurementUnit;
    min_value: number;
    max_value: number;
  }[];
  height_as_reference_only: boolean;
  derived: string[];
  disclaimer: string;
}

export interface BaselineMetric {
  metric_type: string;
  measurement_id: string;
  value: number;
  unit: string;
  measured_at: string;
  superseded_since: boolean;
}

export interface ScenarioMetric {
  metric_type: string;
  value: number;
  unit: string;
  delta_absolute: number;
  delta_percent: number | null;
  clamped: boolean;
}

export interface SimulationComparison {
  simulation_id: string;
  profile_id: string;
  label: string;
  status: SimulationStatus;
  data_kind: "simulation";
  engine: { name: string; version: string };
  baseline_hash: string;
  created_at: string;
  created_by: string;
  result_checksum: string | null;
  baseline: { captured_from: string; metrics: BaselineMetric[] };
  scenario: { metrics: ScenarioMetric[] };
  derived: Record<
    string,
    { baseline: string | null; simulated: string | null; delta_absolute: string | null; components: string }
  >;
  unchanged: string[];
  warnings: string[];
  disclaimer: string;
  banner: string;
}

export const SIMULATION_STATUS_LABEL: Record<SimulationStatus, string> = {
  draft: "Borrador",
  queued: "En cola",
  completed: "Calculado",
  failed: "Falló",
  archived: "Archivado",
};

export const PARAMETER_MODE_LABEL: Record<ParameterMode, string> = {
  delta_absolute: "Cambio absoluto",
  delta_percent: "Cambio porcentual",
  target_value: "Valor objetivo",
};

export const DERIVED_LABEL: Record<string, string> = {
  waist_height: "Cintura / estatura",
  waist_hip: "Cintura / cadera",
};

/** Aviso permanente: se muestra en toda la superficie de simulación. */
export const SIMULATION_WARNING: DataKind = "simulation";

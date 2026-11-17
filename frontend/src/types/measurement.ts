export type MeasurementType = "weight" | "height" | "waist" | "hip" | "chest" | "arm" | "thigh";
export type MeasurementUnit = "kg" | "cm";
export type MeasurementMethod =
  | "manual_tape"
  | "scale"
  | "professional"
  | "self_reported"
  | "other";

export interface MetricSpec {
  metric_type: MeasurementType;
  label: string;
  unit: MeasurementUnit;
  min_value: number;
  max_value: number;
}

export interface MethodOption {
  value: MeasurementMethod;
  label: string;
}

export interface MeasurementCatalog {
  metrics: MetricSpec[];
  methods: MethodOption[];
}

export interface Measurement {
  id: string;
  profile_id: string;
  metric_type: MeasurementType;
  value: number;
  unit: MeasurementUnit;
  measured_at: string;
  method: MeasurementMethod;
  created_by: string;
  notes: string | null;
  recorded_at: string;
  supersedes_id: string | null;
  correction_reason: string | null;
  is_current: boolean;
  kind: "observed";
}

export interface SeriesPoint {
  id: string;
  measured_at: string;
  value: number;
  method: MeasurementMethod;
  corrected: boolean;
}

export interface MeasurementSeries {
  metric_type: MeasurementType;
  unit: MeasurementUnit;
  kind: "observed";
  points: SeriesPoint[];
}

export interface MeasurementCreatePayload {
  metric_type: MeasurementType;
  value: number;
  unit: MeasurementUnit;
  measured_at: string;
  method: MeasurementMethod;
  created_by: string;
  notes?: string | null;
}

export interface MeasurementCorrectionPayload {
  value: number;
  measured_at: string;
  method: MeasurementMethod;
  created_by: string;
  reason: string;
  notes?: string | null;
}
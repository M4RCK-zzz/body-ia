import type { DataKind } from "./dataKind";

export type ReportKind = "measurements_csv" | "measurements_pdf" | "pose_csv" | "pose_pdf";
export type ReportStatus = "queued" | "processing" | "generated" | "failed";

export interface Report {
  id: string;
  profile_id: string;
  kind: ReportKind;
  format: "csv" | "pdf";
  data_kind: DataKind;
  status: ReportStatus;
  date_from: string | null;
  date_to: string | null;
  metrics_json: string[] | null;
  summary_json: Record<string, unknown> | null;
  checksum_sha256: string | null;
  size_bytes: number | null;
  error_message: string | null;
  requested_by: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  download_url: string | null;
}

export interface ReportRequestPayload {
  kind: ReportKind;
  date_from?: string;
  date_to?: string;
}

export const REPORT_KIND_LABEL: Record<ReportKind, string> = {
  measurements_csv: "Mediciones (CSV)",
  measurements_pdf: "Mediciones (PDF)",
  pose_csv: "Pose (CSV)",
  pose_pdf: "Pose (PDF)",
};

export const REPORT_KIND_HELP: Record<ReportKind, string> = {
  measurements_csv: "Una fila por medición vigente + resumen descriptivo. Datos tabulares.",
  measurements_pdf: "Documento paginado con aviso no clínico en cada página.",
  pose_csv: "Metadatos de análisis de pose. Son ESTIMACIONES, no mediciones.",
  pose_pdf: "Documento paginado de estimaciones visuales. No se mezcla con mediciones.",
};

/** Los reportes de pose NUNCA se mezclan con los de mediciones observadas. */
export const REPORT_KINDS_MEASUREMENTS: ReportKind[] = ["measurements_csv", "measurements_pdf"];
export const REPORT_KINDS_POSE: ReportKind[] = ["pose_csv", "pose_pdf"];

export const REPORT_STATUS_LABEL: Record<ReportStatus, string> = {
  queued: "En cola",
  processing: "Generando",
  generated: "Listo",
  failed: "Falló",
};

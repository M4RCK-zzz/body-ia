/** Tipos del análisis de pose (Fase 5). Son siempre estimaciones visuales. */

export type PoseAnalysisStatus = "queued" | "processing" | "completed" | "failed" | "needs_review";

export const POSE_STATUS_LABEL: Record<PoseAnalysisStatus, string> = {
  queued: "En cola",
  processing: "Procesando",
  completed: "Completado",
  failed: "Fallido",
  needs_review: "Requiere revisión",
};

/**
 * Clases de la píldora de estado.
 *
 * Antes `needs_review`/`failed` apuntaban a `bv-alert--warn|error`, que son
 * bloques de aviso (`padding`, `border-radius` y borde pensados para un párrafo):
 * dentro de un `<span class="bv-tag">` se veían como una barra estirada. Ahora
 * usan variantes de etiqueta y la píldora mide su texto.
 */
export const POSE_STATUS_BADGE_CLASS: Record<PoseAnalysisStatus, string> = {
  queued: "bv-tag--status",
  processing: "bv-tag--status",
  completed: "bv-tag--observed",
  needs_review: "bv-tag--warn",
  failed: "bv-tag--error",
};

export interface PoseLandmark {
  index: number;
  x: number | null;
  y: number | null;
  z: number | null;
  visibility: number | null;
}

export interface PoseQualityFlags {
  quality: string;
  flags: string[];
  visible_landmarks: number;
  total_landmarks: number;
  visibility_threshold: number;
  pose_count: number;
  model_version: string;
}

export interface PoseAnalysis {
  id: string;
  media_asset_id: string;
  profile_id: string;
  status: PoseAnalysisStatus;
  created_by: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  attempt_count: number;
  model_name: string | null;
  model_version: string | null;
  quality_flags: PoseQualityFlags | null;
  landmarks: PoseLandmark[] | null;
  error_message: string | null;
  data_kind: "visual_estimate";
  visual_estimate_badge: "ESTIMACIÓN VISUAL";
}

export const POSE_QUALITY_LABEL: Record<string, string> = {
  good: "Buena calidad",
  partial: "Calidad parcial",
  low: "Calidad baja",
};

export const POSE_FLAG_LABEL: Record<string, string> = {
  pose_complete: "Pose completa",
  pose_partial: "Pose parcial (detectados pocos puntos)",
  low_visibility: "Visibilidad baja",
};

export const POSE_BADGE = "ESTIMACIÓN VISUAL" as const;

export function formatDurationMs(ms: number | null): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.floor(ms / 60_000)} min ${Math.round((ms % 60_000) / 1000)} s`;
}

export function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-PE");
}

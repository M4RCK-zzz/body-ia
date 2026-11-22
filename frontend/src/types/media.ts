export type MediaStatus = "uploaded" | "validating" | "ready" | "rejected" | "deleted";

export const MEDIA_STATUS_LABEL: Record<MediaStatus, string> = {
  uploaded: "Subido",
  validating: "Validando",
  ready: "Listo",
  rejected: "Rechazado",
  deleted: "Eliminado",
};

/** Metadatos de un medio capturado. Los bytes solo se sirven vía el endpoint autenticado. */
export interface MediaAsset {
  id: string;
  profile_id: string;
  status: MediaStatus;
  mime_type: string | null;
  size_bytes: number;
  width: number | null;
  height: number | null;
  checksum: string;
  rejection_reason: string | null;
  uploaded_by: string;
  uploaded_at: string;
  ready_at: string | null;
  rejected_at: string | null;
  deleted_at: string | null;
  retention_until: string;
}

export const MEDIA_FORMAT_LABEL: Record<string, string> = {
  "image/jpeg": "JPEG",
  "image/png": "PNG",
  "image/webp": "WebP",
};

export function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function truncateChecksum(checksum: string | null, len = 8): string {
  if (!checksum) return "—";
  if (checksum.length <= len) return checksum;
  return `${checksum.slice(0, len)}…`;
}

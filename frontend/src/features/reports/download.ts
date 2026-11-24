/** Descarga autenticada: el Blob ya viene con el token del usuario. */
export function downloadReport(blob: Blob, filename: string): void {
  const safe = filename.replace(/[^A-Za-z0-9._-]/g, "_").slice(0, 120) || "reporte";
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = safe;
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
  // Revoca en el próximo ciclo para no cortar la descarga en algunos navegadores.
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function reportFilename(report: {
  id: string;
  kind: string;
  format: string;
  data_kind: string;
}): string {
  const label = report.kind.startsWith("pose") ? "pose" : "mediciones";
  const kindTag = report.data_kind === "visual_estimate" ? "estimacion" : "observado";
  return `bodyvision_${label}_${kindTag}_${report.id.slice(0, 8)}.${report.format}`;
}

export function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} kB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

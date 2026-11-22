import { useEffect, useRef, useState, type DragEvent, type ChangeEvent } from "react";
import { useUploadMedia } from "./hooks/useMedia";
import { formatBytes } from "@/types/media";

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const ACCEPTED_MIMES = ["image/jpeg", "image/png", "image/webp"];

interface Props {
  profileId: string;
  readOnly: boolean;
  readOnlyReason?: string;
}

export function CaptureUpload({ profileId, readOnly, readOnlyReason }: Props) {
  const upload = useUploadMedia(profileId);
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<{ name: string; size: number; url: string; file: File } | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    return () => {
      if (preview?.url) URL.revokeObjectURL(preview.url);
    };
  }, [preview]);

  function acceptFile(file: File): boolean {
    setClientError(null);
    if (!ACCEPTED_MIMES.includes(file.type)) {
      setClientError("Formato no soportado. Solo JPEG, PNG y WebP.");
      return false;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setClientError(`El archivo supera el límite de ${formatBytes(MAX_UPLOAD_BYTES)}.`);
      return false;
    }
    if (preview?.url) URL.revokeObjectURL(preview.url);
    setPreview({ name: file.name, size: file.size, url: URL.createObjectURL(file), file });
    return true;
  }

  function onInputChange(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;
    if (files?.[0]) acceptFile(files[0]);
    event.target.value = "";
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) acceptFile(file);
  }

  function onPasteFailure(message: string) {
    setClientError(message);
  }

  async function onUpload() {
    if (!preview) return;
    setClientError(null);
    try {
      await upload.mutateAsync(preview.file);
      if (preview?.url) URL.revokeObjectURL(preview.url);
      setPreview(null);
    } catch (error) {
      onPasteFailure(
        error instanceof Error ? friendlyMessage(error) : "No se pudo subir la captura.",
      );
    }
  }

  function friendlyMessage(error: Error & { code?: string }): string {
    // Errores de la API con codigo estable (HttpError); el mensaje ya es legible.
    if ("code" in error && error.code) return error.message;
    return error.message || "No se pudo subir la captura.";
  }

  if (readOnly) {
    return (
      <section className="bv-panel capture-upload">
        <h2>Subir captura</h2>
        <p className="bv-alert bv-alert--warn">{readOnlyReason ?? "Solo el propietario y editores pueden subir capturas."}</p>
      </section>
    );
  }

  return (
    <section className="bv-panel capture-upload">
      <h2>Subir captura</h2>
      <p className="bv-muted">
        Formatos: JPEG, PNG y WebP · Máximo {formatBytes(MAX_UPLOAD_BYTES)} · Los bytes se almacenan privadamente; tu navegador nunca accede al almacenamiento.
      </p>
      <div
        className={`capture-upload__drop ${isDragging ? "is-dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        role="button"
        tabIndex={0}
        aria-label="Arrastra un archivo aquí o haz clic para seleccionar"
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
      >
        {preview ? (
          <img src={preview.url} alt="Vista previa de la captura" className="capture-upload__preview" />
        ) : (
          <div className="capture-upload__placeholder">
            <strong>Arrastra la foto aquí o haz clic</strong>
            <span>o selecciona un archivo (.jpg, .png, .webp)</span>
          </div>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
        onChange={onInputChange}
        className="capture-upload__input"
        aria-hidden="true"
        tabIndex={-1}
      />
      {preview ? (
        <div className="capture-upload__meta">
          <span title={preview.name}>{preview.name}</span>
          <span>{formatBytes(preview.size)}</span>
        </div>
      ) : null}
      {clientError ? <p role="alert" className="bv-alert bv-alert--error">{clientError}</p> : null}
      {upload.isSuccess ? <p className="bv-alert bv-alert--info">✓ Captura subida correctamente.</p> : null}
      <button
        type="button"
        className="bv-btn bv-btn--primary"
        disabled={!preview || upload.isPending}
        onClick={onUpload}
      >
        {upload.isPending ? "Subiendo…" : "Subir captura"}
      </button>
    </section>
  );
}

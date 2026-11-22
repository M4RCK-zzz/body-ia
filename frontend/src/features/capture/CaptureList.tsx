import { useEffect, useMemo, useState } from "react";
import { useDeleteMedia, useMediaContent } from "./hooks/useMedia";
import { mediaApi } from "@/services/api/media";
import { formatBytes, MEDIA_FORMAT_LABEL, MEDIA_STATUS_LABEL, truncateChecksum, type MediaAsset } from "@/types/media";
import { POSE_STATUS_BADGE_CLASS, POSE_STATUS_LABEL, type PoseAnalysis } from "@/types/pose";
import { useEnqueuePose, usePoseFromAsset } from "@/features/pose/hooks/usePose";
import { Link } from "react-router-dom";

interface Props {
  profileId: string;
  assets: MediaAsset[];
  total: number;
  readOnly: boolean;
}

function AssetThumbnail({ asset }: { asset: MediaAsset }) {
  const query = useMediaContent(asset.status === "ready" ? asset.id : null);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!query.data) return;
    const url = URL.createObjectURL(query.data);
    setObjectUrl(url);
    return () => {
      URL.revokeObjectURL(url);
      setObjectUrl(null);
    };
  }, [query.data]);

  if (asset.status !== "ready") {
    return (
      <div className="capture-list__no-image" role="img" aria-label="Sin vista previa">
        ✕
      </div>
    );
  }
  if (query.isLoading) return <div className="capture-list__no-image">Cargando…</div>;
  if (query.error || !objectUrl) return <div className="capture-list__no-image">—</div>;
  return <img src={objectUrl} alt="Vista previa de captura" className="capture-list__thumb" loading="lazy" />;
}

function statusBadgeClass(status: MediaAsset["status"]): string {
  switch (status) {
    case "ready": return "bv-tag--observed";
    case "rejected": return "bv-alert--error";
    case "deleted": return "bv-alert--warn";
    default: return "bv-tag--status";
  }
}

function PoseCardSection({ asset, readOnly }: { asset: MediaAsset; readOnly: boolean }) {
  const query = usePoseFromAsset(asset.id);
  const enqueue = useEnqueuePose(asset.id, asset.profile_id);
  const latest: PoseAnalysis | undefined = query.data?.items[0];
  const active = latest?.status === "queued" || latest?.status === "processing";
  const canEnqueue = asset.status === "ready" && !readOnly && !active;

  async function onEnqueue() {
    try {
      await enqueue.mutateAsync();
    } catch {
      /* el botón queda habilitado; el error se muestra abajo */
    }
  }

  const errorMsg = enqueue.error?.message;

  return (
    <div className="capture-list__pose">
      {query.isLoading ? (
        <span className="bv-muted">Cargando análisis…</span>
      ) : latest ? (
        <>
          <span className={`bv-tag ${POSE_STATUS_BADGE_CLASS[latest.status]}`}>
            {POSE_STATUS_LABEL[latest.status].toUpperCase()}
          </span>
          <Link className="bv-btn bv-btn--small" to={`/analyses/${latest.id}`}>
            Ver análisis
          </Link>
        </>
      ) : (
        <button
          type="button"
          className="bv-btn bv-btn--small"
          disabled={!canEnqueue || enqueue.isPending}
          onClick={onEnqueue}
        >
          {enqueue.isPending ? "Encolando…" : "Analizar pose"}
        </button>
      )}
      {errorMsg ? <span className="bv-muted" style={{ color: "#fca5a5" }}>{errorMsg}</span> : null}
    </div>
  );
}

export function CaptureList({ profileId, assets, total, readOnly }: Props) {
  const deleteMutation = useDeleteMedia(profileId);
  const sorted = useMemo(() => assets, [assets]);

  function onDelete(asset: MediaAsset) {
    if (!window.confirm("¿Eliminar esta captura? El archivo se borrará físicamente.")) return;
    deleteMutation.mutate(asset.id);
  }

  async function onDownload(asset: MediaAsset) {
    const blob = await mediaApi.content(asset.id).catch(() => null);
    if (!blob) {
      window.alert("No se pudo descargar la captura.");
      return;
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `captura-${asset.id.slice(0, 8)}.${asset.mime_type?.endsWith("webp") ? "webp" : asset.mime_type?.endsWith("png") ? "png" : "jpg"}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }

  async function onOpen(asset: MediaAsset) {
    const blob = await mediaApi.content(asset.id).catch(() => null);
    if (!blob) {
      window.alert("No se pudo abrir la captura.");
      return;
    }
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }

  if (sorted.length === 0) {
    return (
      <p className="bv-muted">
        Sin capturas en este expediente todavía. Las capturas aparecen aquí después de subirlas.
      </p>
    );
  }

  return (
    <div className="capture-list">
      {sorted.map((asset) => (
        <article key={asset.id} className="capture-list__card">
          <div className="capture-list__media">
            <AssetThumbnail asset={asset} />
          </div>
          <div className="capture-list__body">
            <div className="capture-list__row">
              <span className={`bv-tag ${statusBadgeClass(asset.status)}`}>
                {MEDIA_STATUS_LABEL[asset.status]}
              </span>
              {asset.mime_type ? (
                <span className="bv-muted">{MEDIA_FORMAT_LABEL[asset.mime_type] ?? asset.mime_type}</span>
              ) : null}
              {asset.width && asset.height ? (
                <span className="bv-muted">
                  {asset.width} × {asset.height} px
                </span>
              ) : null}
            </div>
            <p className="capture-list__meta">
              {formatBytes(asset.size_bytes)} · check {truncateChecksum(asset.checksum)} · subida{" "}
              {new Date(asset.uploaded_at).toLocaleString("es-PE")}
            </p>
            <p className="capture-list__meta">Retención hasta {new Date(asset.retention_until).toLocaleDateString("es-PE")}</p>
            <p className="capture-list__meta">Subida por {asset.uploaded_by}</p>
            {asset.status === "rejected" ? (
              <p className="capture-list__reason">Motivo: {asset.rejection_reason}</p>
            ) : null}
            <div className="capture-list__actions">
              {asset.status === "ready" ? (
                <>
                  <button type="button" className="bv-btn bv-btn--small" onClick={() => onOpen(asset)}>
                    Abrir
                  </button>
                  <button type="button" className="bv-btn bv-btn--small" onClick={() => onDownload(asset)}>
                    Descargar
                  </button>
                </>
              ) : null}
              {!readOnly && asset.status !== "deleted" ? (
                <button type="button" className="bv-btn bv-btn--small bv-btn--danger" onClick={() => onDelete(asset)} disabled={deleteMutation.isPending}>
                  Eliminar
                </button>
              ) : null}
            </div>
            {asset.status !== "deleted" ? (
              <PoseCardSection asset={asset} readOnly={readOnly} />
            ) : null}
          </div>
        </article>
      ))}
      <p className="bv-muted">{total} captura{total === 1 ? "" : "s"} en este expediente</p>
    </div>
  );
}

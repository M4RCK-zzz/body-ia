from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import UUID

from app.core.clock import utcnow
from app.core.errors import (
    BusinessRuleError,
    FileTooLargeError,
    MediaRejectedError,
    NotFoundError,
    UnsupportedMediaTypeError,
)
from app.domain.access import AccessLevel, ConsentPurpose
from app.domain.identity import AuditAction
from app.domain.media import (
    MediaMime,
    MediaStatus,
    new_storage_key,
)
from app.domain.profiles import ProfileStatus
from app.integrations.storage import StorageBackend
from app.models.identity import User
from app.models.media import MediaAsset
from app.repositories.media_repository import MediaRepository
from app.services.access_guard import AccessGuard
from app.services.audit_service import AuditRecorder
from app.services.consent_service import ConsentService
from app.services.media_validation import sanitize_image
from app.services.ports import Transaction

logger = logging.getLogger(__name__)


class MediaService:
    """Captura segura (Fase 4): validación, almacenamiento privado, retención y auditoría."""

    def __init__(
        self,
        guard: AccessGuard,
        media: MediaRepository,
        storage: StorageBackend,
        consents: ConsentService,
        audit: AuditRecorder,
        tx: Transaction,
        clock: Callable[[], datetime] = utcnow,
        *,
        max_upload_bytes: int,
        max_pixels: int,
        retention_days: int,
    ) -> None:
        self._guard = guard
        self._media = media
        self._storage = storage
        self._consents = consents
        self._audit = audit
        self._tx = tx
        self._clock = clock
        self._max_upload_bytes = max_upload_bytes
        self._max_pixels = max_pixels
        self._retention_days = retention_days

    @property
    def max_upload_bytes(self) -> int:
        return self._max_upload_bytes

    # --- internas ---

    def _require_write(self, actor: User, profile_id: UUID):
        profile, _ = self._guard.require(profile_id, actor, AccessLevel.EDITOR)
        if profile.status != ProfileStatus.ACTIVE.value:
            raise BusinessRuleError(
                "El expediente no está activo: no admite capturas."
            )
        self._consents.ensure_valid(profile_id, ConsentPurpose.DATA_PROCESSING)
        return profile

    def _asset_for(self, asset_id: UUID) -> MediaAsset:
        asset = self._media.get(asset_id)
        if asset is None:
            raise NotFoundError("Archivo no encontrado.")
        return asset

    # --- operaciones ---

    def upload(
        self,
        actor: User,
        profile_id: UUID,
        *,
        data: bytes,
        declared_mime: str | None,
    ) -> MediaAsset:
        self._require_write(actor, profile_id)
        if len(data) > self._max_upload_bytes:
            if self._max_upload_bytes >= 1024 * 1024:
                limit_label = f"{self._max_upload_bytes // (1024 * 1024)} MB"
            else:
                limit_label = f"{self._max_upload_bytes} bytes"
            raise FileTooLargeError(
                f"El archivo supera el límite de {limit_label}."
            )

        mime = (declared_mime or "").lower().split(";")[0].strip()
        if mime not in {m.value for m in MediaMime}:
            raise UnsupportedMediaTypeError(
                "Tipo de archivo no soportado. Solo JPEG, PNG y WebP."
            )

        now = self._clock()
        retention_until = now + timedelta(days=self._retention_days)

        try:
            fresh = sanitize_image(data, max_pixels=self._max_pixels)
        except MediaRejectedError as exc:
            # Metadatos del intento, sin bytes: evidencia de la denegación.
            asset = MediaAsset(
                profile_id=profile_id,
                storage_key=None,
                mime_type=None,
                size_bytes=len(data),
                width=None,
                height=None,
                checksum=hashlib.sha256(data).hexdigest(),
                status=MediaStatus.REJECTED.value,
                rejection_reason=(exc.message or "rejected")[:300],
                uploaded_by_snapshot=actor.full_name,
                uploaded_by_user_id=actor.id,
                uploaded_at=now,
                rejected_at=now,
                retention_until=retention_until,
            )
            self._media.add(asset)
            self._audit.record(
                AuditAction.MEDIA_REJECTED,
                actor_id=actor.id,
                resource_type="media_asset",
                resource_id=str(asset.id),
                profile_id=profile_id,
                detail={
                    "reason": asset.rejection_reason,
                    "declared_mime": mime or None,
                    "size_bytes": len(data),
                },
            )
            self._tx.commit()
            raise exc

        key = new_storage_key(fresh.mime)
        asset = MediaAsset(
            profile_id=profile_id,
            storage_key=key,
            mime_type=fresh.mime,
            size_bytes=fresh.size_bytes,
            width=fresh.width,
            height=fresh.height,
            checksum=fresh.checksum,
            status=MediaStatus.VALIDATING.value,
            uploaded_by_snapshot=actor.full_name,
            uploaded_by_user_id=actor.id,
            uploaded_at=now,
            retention_until=retention_until,
        )
        self._media.add(asset)
        try:
            self._storage.put(key, fresh.data)
        except Exception:
            self._tx.rollback()
            raise
        asset.status = MediaStatus.READY.value
        asset.ready_at = now
        self._media.save(asset)
        self._audit.record(
            AuditAction.MEDIA_UPLOADED,
            actor_id=actor.id,
            resource_type="media_asset",
            resource_id=str(asset.id),
            profile_id=profile_id,
            detail={
                "mime_type": fresh.mime,
                "size_bytes": fresh.size_bytes,
                "checksum": fresh.checksum,
            },
        )
        self._tx.commit()
        return asset

    def list_assets(
        self,
        actor: User,
        profile_id: UUID,
        *,
        status: MediaStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MediaAsset], int]:
        self._guard.require(profile_id, actor, AccessLevel.VIEWER)
        limit = min(max(limit, 1), 200)
        return self._media.list_page(
            profile_id=profile_id,
            status=status.value if status is not None else None,
            limit=limit,
            offset=offset,
        )

    def get(self, actor: User, asset_id: UUID) -> MediaAsset:
        asset = self._asset_for(asset_id)
        self._guard.require(asset.profile_id, actor, AccessLevel.VIEWER)
        return asset

    def content(
        self, actor: User, asset_id: UUID
    ) -> tuple[MediaAsset, bytes]:
        asset = self.get(actor, asset_id)
        if asset.status != MediaStatus.READY.value:
            raise NotFoundError("Archivo no disponible.")
        try:
            data = self._storage.get(asset.storage_key)
        except FileNotFoundError as exc:
            logger.error("archivo registrado ausente en storage: %s", asset.id)
            raise NotFoundError("Archivo no disponible.") from exc
        return asset, data

    def delete(self, actor: User, asset_id: UUID) -> MediaAsset:
        asset = self._asset_for(asset_id)
        self._guard.require(asset.profile_id, actor, AccessLevel.EDITOR)
        if asset.status == MediaStatus.DELETED.value:
            return asset
        now = self._clock()
        asset.status = MediaStatus.DELETED.value
        asset.deleted_at = now
        asset.deleted_by_user_id = actor.id
        if asset.storage_key:
            try:
                self._storage.delete(asset.storage_key)
            except Exception:
                logger.warning("No se pudo borrar físicamente la clave de %s", asset.id)
        self._audit.record(
            AuditAction.MEDIA_DELETED,
            actor_id=actor.id,
            resource_type="media_asset",
            resource_id=str(asset.id),
            profile_id=asset.profile_id,
            detail={"mime_type": asset.mime_type, "size_bytes": asset.size_bytes},
        )
        self._tx.commit()
        return asset

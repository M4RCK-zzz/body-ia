from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.core.clock import utcnow
from app.core.errors import BusinessRuleError, NotFoundError
from app.domain.access import AccessLevel, ConsentPurpose
from app.domain.identity import AuditAction
from app.domain.media import MediaStatus
from app.domain.pose import (
    PoseAnalysisStatus,
)
from app.domain.profiles import ProfileStatus
from app.models.identity import User
from app.models.pose import PoseAnalysis
from app.repositories.media_repository import MediaRepository
from app.repositories.pose_repository import PoseRepository
from app.services.access_guard import AccessGuard
from app.services.audit_service import AuditRecorder
from app.services.consent_service import ConsentService
from app.services.ports import Transaction

logger = logging.getLogger(__name__)


class PoseService:
    """Cola de análisis de pose (Fase 5). No ejecuta el modelo.

    Idempotencia: una asset solo puede tener una tarea activa (queued/processing).
    Re-POST devuelve la misma tarea con 200.
    """

    def __init__(
        self,
        guard: AccessGuard,
        media: MediaRepository,
        pose: PoseRepository,
        consents: ConsentService,
        audit: AuditRecorder,
        tx: Transaction,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._guard = guard
        self._media = media
        self._pose = pose
        self._consents = consents
        self._audit = audit
        self._tx = tx
        self._clock = clock

    # --- internas ---

    def _require_write(self, actor: User, profile_id: UUID):
        profile, _ = self._guard.require(profile_id, actor, AccessLevel.EDITOR)
        if profile.status != ProfileStatus.ACTIVE.value:
            raise BusinessRuleError(
                "El expediente no está activo: no admite análisis."
            )
        self._consents.ensure_valid(profile_id, ConsentPurpose.DATA_PROCESSING)
        return profile

    def _asset_for(self, asset_id: UUID):
        asset = self._media.get(asset_id)
        if asset is None:
            raise NotFoundError("Archivo no encontrado.")
        return asset

    # --- operaciones ---

    def enqueue(self, actor: User, asset_id: UUID) -> tuple[PoseAnalysis, bool]:
        """Crea la tarea o devuelve la activa existente (idempotente).

        Devuelve (analysis, created).
        """
        asset = self._asset_for(asset_id)
        self._require_write(actor, asset.profile_id)
        if asset.status != MediaStatus.READY.value:
            raise BusinessRuleError(
                "El archivo no está listo (ready): solo los archivos validados "
                "admiten análisis de pose."
            )
        existing = self._pose.find_active_for_asset(asset.id)
        if existing is not None:
            return existing, False

        now = self._clock()
        analysis = PoseAnalysis(
            media_asset_id=asset.id,
            profile_id=asset.profile_id,
            status=PoseAnalysisStatus.QUEUED.value,
            created_by_snapshot=actor.full_name,
            created_by_user_id=actor.id,
            attempt_count=1,
            created_at=now,
        )
        self._pose.add(analysis)
        self._audit.record(
            AuditAction.POSE_QUEUED,
            actor_id=actor.id,
            resource_type="pose_analysis",
            resource_id=str(analysis.id),
            profile_id=asset.profile_id,
            detail={"media_asset_id": str(asset.id), "profile_id": str(asset.profile_id)},
        )
        self._tx.commit()
        return analysis, True

    def get(self, actor: User, analysis_id: UUID) -> PoseAnalysis:
        analysis = self._pose.get(analysis_id)
        if analysis is None:
            raise NotFoundError("Análisis de pose no encontrado.")
        self._guard.require(analysis.profile_id, actor, AccessLevel.VIEWER)
        return analysis

    def list_for_asset(
        self,
        actor: User,
        asset_id: UUID,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PoseAnalysis], int]:
        asset = self._asset_for(asset_id)
        self._guard.require(asset.profile_id, actor, AccessLevel.VIEWER)
        limit = min(max(limit, 1), 200)
        return self._pose.list_page_by_asset(
            media_asset_id=asset.id,
            status=status,
            limit=limit,
            offset=offset,
        )

    def list_for_profile(
        self,
        actor: User,
        profile_id: UUID,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PoseAnalysis], int]:
        self._guard.require(profile_id, actor, AccessLevel.VIEWER)
        limit = min(max(limit, 1), 200)
        return self._pose.list_page(
            profile_id=profile_id,
            status=status,
            limit=limit,
            offset=offset,
        )

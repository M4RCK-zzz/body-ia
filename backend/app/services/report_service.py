from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.core.clock import utcnow
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.domain.access import AccessLevel
from app.domain.identity import AuditAction
from app.domain.measurements import MeasurementType
from app.domain.reports import (
    CONTENT_TYPES,
    REPORT_DATA_KIND,
    REPORT_FORMAT,
    REPORT_LABEL,
    ReportKind,
    ReportStatus,
)
from app.integrations.storage import StorageBackend
from app.models.identity import User
from app.models.report import Report
from app.repositories.report_repository import ReportRepository
from app.services.access_guard import AccessGuard
from app.services.audit_service import AuditRecorder
from app.services.ports import Transaction

logger = logging.getLogger(__name__)


class ReportService:
    """Solicitud y descarga de reportes trazables (Fase 7).

    La generación es asíncrona (`app.workers.report_worker`); aquí solo se
    encola, se consulta y se sirve el binario ya generado.
    """

    def __init__(
        self,
        guard: AccessGuard,
        reports: ReportRepository,
        storage: StorageBackend,
        audit: AuditRecorder,
        tx: Transaction,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._guard = guard
        self._reports = reports
        self._storage = storage
        self._audit = audit
        self._tx = tx
        self._clock = clock

    # --- internas ---

    def _report_for(self, report_id: UUID) -> Report:
        report = self._reports.get(report_id)
        if report is None:
            raise NotFoundError("Reporte no encontrado.")
        return report

    def _profile_code(self, report: Report) -> str:
        # El código se congela en `parameters_json` al solicitar; así el reporte
        # sigue siendo legible aunque el expediente se renombre después.
        params = report.parameters_json or {}
        return str(params.get("profile_code") or "—")

    # --- operaciones ---

    def request(
        self,
        actor: User,
        profile_id: UUID,
        *,
        kind: ReportKind,
        date_from: datetime | None,
        date_to: datetime | None,
        metric_types: list[MeasurementType] | None = None,
    ) -> tuple[Report, bool]:
        """Encola un reporte. Devuelve (report, created).

        Idempotente: si ya hay un reporte idéntico en cola/proceso, se devuelve
        ese mismo (200) en lugar de duplicarlo.
        """
        if date_from is not None and date_to is not None and date_from > date_to:
            raise BusinessRuleError(
                "El rango de fechas es inválido: el inicio es posterior al fin."
            )

        profile, _ = self._guard.require(profile_id, actor, AccessLevel.VIEWER)
        data_kind = REPORT_DATA_KIND[kind]

        # Las estimaciones de pose no se exportan mezcladas con mediciones: cada
        # tipo de reporte tiene su propio DataKind y su propio aviso.
        metrics = None
        if data_kind == "observed":
            metrics = (
                [metric.value for metric in metric_types]
                if metric_types
                else None
            )

        existing = self._reports.find_active_for_profile(
            profile_id=profile.id,
            kind=kind.value,
            date_from=date_from,
            date_to=date_to,
        )
        if existing is not None and (existing.metrics_json or None) == metrics:
            return existing, False

        now = self._clock()
        report = Report(
            profile_id=profile.id,
            kind=kind.value,
            format=REPORT_FORMAT[kind],
            data_kind=data_kind,
            status=ReportStatus.QUEUED.value,
            date_from=date_from,
            date_to=date_to,
            metrics_json=metrics,
            parameters_json={
                "profile_code": profile.display_code,
                "requested_by": actor.full_name,
                "requested_at": now.isoformat(),
                "report_label": REPORT_LABEL[kind],
                "mime_type": CONTENT_TYPES[REPORT_FORMAT[kind]],
            },
            requested_by_snapshot=actor.full_name,
            requested_by_user_id=actor.id,
            attempt_count=1,
            created_at=now,
        )
        self._reports.add(report)
        self._audit.record(
            AuditAction.REPORT_REQUESTED,
            actor_id=actor.id,
            resource_type="report",
            resource_id=str(report.id),
            profile_id=profile.id,
            detail={
                "kind": report.kind,
                "format": report.format,
                "data_kind": report.data_kind,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
            },
        )
        self._tx.commit()
        return report, True

    def get(self, actor: User, report_id: UUID) -> Report:
        report = self._report_for(report_id)
        self._guard.require(report.profile_id, actor, AccessLevel.VIEWER)
        return report

    def list_for_profile(
        self,
        actor: User,
        profile_id: UUID,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Report], int]:
        self._guard.require(profile_id, actor, AccessLevel.VIEWER)
        limit = min(max(limit, 1), 200)
        return self._reports.list_page(
            profile_id=profile_id, status=status, limit=limit, offset=offset
        )

    def list_mine(
        self, actor: User, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[Report], int]:
        limit = min(max(limit, 1), 200)
        return self._reports.list_page_for_user(
            requested_by_user_id=actor.id, status=status, limit=limit, offset=offset
        )

    def content(self, actor: User, report_id: UUID) -> tuple[Report, bytes]:
        report = self.get(actor, report_id)
        if report.status != ReportStatus.GENERATED.value or not report.storage_key:
            raise ConflictError("El reporte aún no está disponible para descarga.")
        try:
            data = self._storage.get(report.storage_key)
        except FileNotFoundError as exc:
            logger.error("reporte registrado sin binario en storage: %s", report.id)
            raise NotFoundError("El archivo del reporte no está disponible.") from exc

        # Integridad: si el binario no coincide con el checksum registrado, no se
        # sirve. Evita descargar un archivo alterado fuera del flujo del worker.
        digest = hashlib.sha256(data).hexdigest()
        if report.checksum_sha256 and digest != report.checksum_sha256:
            logger.error("checksum del reporte %s no coincide", report.id)
            raise ConflictError(
                "El archivo del reporte no supera la verificación de integridad."
            )

        self._audit.record(
            AuditAction.REPORT_DOWNLOADED,
            actor_id=actor.id,
            resource_type="report",
            resource_id=str(report.id),
            profile_id=report.profile_id,
            detail={"kind": report.kind, "checksum_sha256": report.checksum_sha256},
        )
        self._tx.commit()
        return report, data

    def profile_code(self, report: Report) -> str:
        return self._profile_code(report)

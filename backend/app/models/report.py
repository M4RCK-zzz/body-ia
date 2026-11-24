from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base
from app.domain.reports import ReportStatus


class Report(Base):
    """Reporte trazable generado (Fase 7).

    El binario NUNCA se guarda en PostgreSQL: vive en el storage privado bajo
    `storage_key` (UUID + extensión) y se descarga por endpoint autenticado.

    Invariantes (CHECK en BD):
    - `queued`: sin started_at/completed_at, sin storage_key ni checksum.
    - `processing`: started_at y sin completed_at.
    - `generated`: started_at, completed_at, storage_key, checksum y size.
    - `failed`: started_at, completed_at y error_message; sin storage_key.
    """

    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('measurements_csv', 'measurements_pdf', 'pose_csv', 'pose_pdf')",
            name="kind",
        ),
        CheckConstraint(
            "status IN ('queued', 'processing', 'generated', 'failed')",
            name="status",
        ),
        CheckConstraint(
            "(status = 'queued' AND started_at IS NULL AND completed_at IS NULL "
            "AND storage_key IS NULL AND checksum_sha256 IS NULL) "
            "OR (status = 'processing' AND started_at IS NOT NULL AND completed_at IS NULL "
            "AND storage_key IS NULL AND checksum_sha256 IS NULL) "
            "OR (status = 'generated' AND started_at IS NOT NULL AND completed_at IS NOT NULL "
            "AND storage_key IS NOT NULL AND checksum_sha256 IS NOT NULL "
            "AND size_bytes IS NOT NULL AND error_message IS NULL) "
            "OR (status = 'failed' AND started_at IS NOT NULL AND completed_at IS NOT NULL "
            "AND storage_key IS NULL AND checksum_sha256 IS NULL "
            "AND error_message IS NOT NULL)",
            name="lifecycle",
        ),
        CheckConstraint(
            "date_from IS NULL OR date_to IS NULL OR date_from <= date_to",
            name="period",
        ),
        Index("ix_reports_profile_created_at", "profile_id", "created_at"),
        Index("ix_reports_status_created_at", "status", "created_at"),
        Index("ix_reports_requested_by", "requested_by_user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="RESTRICT")
    )
    kind: Mapped[str] = mapped_column(String(32))
    format: Mapped[str] = mapped_column(String(8))
    data_kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(
        String(16),
        default=ReportStatus.QUEUED.value,
        server_default=ReportStatus.QUEUED.value,
    )
    date_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Selección de métricas solicitada (None = todas las habilitadas del catálogo).
    metrics_json: Mapped[list[str] | None] = mapped_column(JSONB)
    # Config congelada en el momento de la petición: catálogo, ventana, aviso legal.
    parameters_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Metadatos del resultado: conteos, rango real cubierto, versión del generador.
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    storage_key: Mapped[str | None] = mapped_column(String(96))
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(300))
    requested_by_snapshot: Mapped[str] = mapped_column(String(120))
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    @property
    def requested_by(self) -> str:
        return self.requested_by_snapshot

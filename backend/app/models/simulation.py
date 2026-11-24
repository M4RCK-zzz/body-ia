from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base
from app.domain.enums import DataKind
from app.domain.measurements import MeasurementType
from app.domain.simulation import SimulationStatus


class Simulation(Base):
    """Escenario hipotético (Fase 8).

    `DataKind.SIMULATION` siempre: nunca se mezcla con mediciones observadas ni con
    estimaciones de pose. Los binarios no existen aquí: el resultado es JSONB con
    `result_checksum`; la base usada vive en `simulation_baselines`.

    Invariantes (CHECK en BD):
    - `draft`: sin hitos ni resultado.
    - `queued`: `queued_at`; sin `started_at`/`completed_at`/resultado.
    - `completed`: `started_at` + `completed_at` + resultado + checksum.
    - `failed`: `completed_at` + `error_message`; sin resultado.
    - `archived`: estado de cierre; conserva el resultado si lo hubo y el
      `error_message` si falló. Nunca inventa un resultado.
    """

    __tablename__ = "simulations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'queued', 'completed', 'failed', 'archived')",
            name="status",
        ),
        CheckConstraint("data_kind = 'simulation'", name="data_kind"),
        CheckConstraint(
            "(status = 'draft' AND queued_at IS NULL AND started_at IS NULL "
            "AND completed_at IS NULL AND archived_at IS NULL "
            "AND result_json IS NULL AND result_checksum IS NULL "
            "AND error_message IS NULL) "
            "OR (status = 'queued' AND queued_at IS NOT NULL AND started_at IS NULL "
            "AND completed_at IS NULL AND archived_at IS NULL "
            "AND result_json IS NULL AND result_checksum IS NULL "
            "AND error_message IS NULL) "
            "OR (status = 'completed' AND queued_at IS NOT NULL AND started_at IS NOT NULL "
            "AND completed_at IS NOT NULL AND archived_at IS NULL "
            "AND result_json IS NOT NULL AND result_checksum IS NOT NULL "
            "AND error_message IS NULL) "
            "OR (status = 'failed' AND completed_at IS NOT NULL "
            "AND result_json IS NULL AND result_checksum IS NULL "
            "AND error_message IS NOT NULL) "
            "OR (status = 'archived' AND archived_at IS NOT NULL "
            "AND ((result_json IS NULL AND result_checksum IS NULL) "
            "OR (result_json IS NOT NULL AND result_checksum IS NOT NULL)))",
            name="lifecycle",
        ),
        CheckConstraint(
            "jsonb_typeof(parameters_json) = 'object' AND parameters_json <> '{}'::jsonb",
            name="parameters_shape",
        ),
        CheckConstraint("length(btrim(label)) BETWEEN 1 AND 80", name="label_len"),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at", name="timeline"
        ),
        Index("ix_simulations_profile_created_at", "profile_id", "created_at"),
        Index(
            "ix_simulations_queue",
            "queued_at",
            postgresql_where=text("status = 'queued'"),
        ),
        Index("ix_simulations_creator", "created_by_user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="RESTRICT")
    )
    label: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(
        String(16),
        default=SimulationStatus.DRAFT.value,
        server_default=SimulationStatus.DRAFT.value,
    )
    data_kind: Mapped[str] = mapped_column(
        String(16),
        default=DataKind.SIMULATION.value,
        server_default=DataKind.SIMULATION.value,
    )
    engine_name: Mapped[str] = mapped_column(String(40))
    engine_version: Mapped[str] = mapped_column(String(20))
    engine_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    baseline_hash: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    result_checksum: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(String(500))
    error_message: Mapped[str | None] = mapped_column(String(300))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_by_snapshot: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class SimulationBaseline(Base):
    """Referencia base inmutable: mediciones observadas copiadas al crear el escenario.

    `ON DELETE RESTRICT` en ambos lados: una medición usada como base no puede
    desaparecer, y la fila de base no se borra en cascada con el escenario.
    """

    __tablename__ = "simulation_baselines"
    __table_args__ = (
        UniqueConstraint("simulation_id", "metric_type", name="uq_simulation_metric"),
        Index("ix_simulation_baselines_measurement", "measurement_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    simulation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("simulations.id", ondelete="RESTRICT")
    )
    metric_type: Mapped[str] = mapped_column(String(32))
    measurement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("measurements.id", ondelete="RESTRICT")
    )
    value_snapshot: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    unit: Mapped[str] = mapped_column(String(8))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )


ALLOWED_BASELINE_METRICS = tuple(metric.value for metric in MeasurementType)

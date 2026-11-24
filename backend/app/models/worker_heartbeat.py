from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkerHeartbeat(Base):
    """Latido de cada worker (Fase 9).

    Una fila por worker lógico (`pose`, `report`, `simulation`, `retention`). Se
    actualiza al final de cada pasada: si `last_seen_at` envejece, el worker está
    caído o bloqueado y `/api/health/workers` lo dice.
    """

    __tablename__ = "worker_heartbeats"

    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    worker_version: Mapped[str] = mapped_column(String(20), nullable=False, default="0.1.0")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)

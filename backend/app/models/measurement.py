import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.clock import utcnow
from app.db.base import Base

class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (
        CheckConstraint("value > 0", name="value_positive"),
        CheckConstraint(
            "(supersedes_id IS NULL) = (correction_reason IS NULL)", name="correction_has_reason"
        ),
        Index("ix_measurements_profile_metric_time", "profile_id", "metric_type", "measured_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profiles.id", ondelete="RESTRICT"))
    metric_type: Mapped[str] = mapped_column(String(32))
    value: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    unit: Mapped[str] = mapped_column(String(8))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    method: Mapped[str] = mapped_column(String(32))
    created_by: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(String(500))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("measurements.id", ondelete="RESTRICT"), unique=True
    )
    correction_reason: Mapped[str | None] = mapped_column(String(300))

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
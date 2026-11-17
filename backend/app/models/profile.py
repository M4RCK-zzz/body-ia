import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.clock import utcnow
from app.db.base import Base
from app.domain.profiles import ProfileStatus

class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived', 'restricted')", name="status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    display_code: Mapped[str] = mapped_column(String(40), unique=True)
    status: Mapped[str] = mapped_column(
        String(16),
        default=ProfileStatus.ACTIVE.value,
        server_default=ProfileStatus.ACTIVE.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
"""Reportes trazables (Fase 7): tabla reports

Revision ID: 0007
Revises: 0006

El binario del reporte (CSV/PDF) no se guarda en PostgreSQL: solo se persiste
la clave del storage privado, el checksum SHA-256 y los metadatos de auditoría.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("format", sa.String(8), nullable=False),
        sa.Column("data_kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("date_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metrics_json", postgresql.JSONB(), nullable=True),
        sa.Column("parameters_json", postgresql.JSONB(), nullable=True),
        sa.Column("summary_json", postgresql.JSONB(), nullable=True),
        sa.Column("storage_key", sa.String(96), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(300), nullable=True),
        sa.Column("requested_by_snapshot", sa.String(120), nullable=False),
        sa.Column(
            "requested_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "kind IN ('measurements_csv', 'measurements_pdf', 'pose_csv', 'pose_pdf')",
            name="ck_reports_kind",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'generated', 'failed')",
            name="ck_reports_status",
        ),
        sa.CheckConstraint(
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
            name="ck_reports_lifecycle",
        ),
        sa.CheckConstraint(
            "date_from IS NULL OR date_to IS NULL OR date_from <= date_to",
            name="ck_reports_period",
        ),
    )
    op.create_index("ix_reports_profile_created_at", "reports", ["profile_id", "created_at"])
    op.create_index("ix_reports_status_created_at", "reports", ["status", "created_at"])
    op.create_index(
        "ix_reports_requested_by", "reports", ["requested_by_user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_reports_requested_by", table_name="reports")
    op.drop_index("ix_reports_status_created_at", table_name="reports")
    op.drop_index("ix_reports_profile_created_at", table_name="reports")
    op.drop_table("reports")

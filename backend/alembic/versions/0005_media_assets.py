"""Captura segura (Fase 4): tabla media_assets y retención

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(96), nullable=True, unique=True),
        sa.Column("mime_type", sa.String(32), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="uploaded"),
        sa.Column("rejection_reason", sa.String(300), nullable=True),
        sa.Column("uploaded_by_snapshot", sa.String(120), nullable=False),
        sa.Column(
            "uploaded_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "deleted_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('uploaded', 'validating', 'ready', 'rejected', 'deleted')",
            name="ck_media_assets_status",
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_media_assets_size_positive"),
        sa.CheckConstraint(
            "status = 'rejected' OR (width > 0 AND height > 0)",
            name="ck_media_assets_dims_positive",
        ),
        sa.CheckConstraint(
            "(status IN ('rejected', 'deleted') OR storage_key IS NOT NULL)",
            name="ck_media_assets_storage_key",
        ),
    )
    op.create_index("ix_media_assets_profile_id", "media_assets", ["profile_id"])
    op.create_index("ix_media_assets_status", "media_assets", ["status"])


def downgrade() -> None:
    op.drop_index("ix_media_assets_status", table_name="media_assets")
    op.drop_index("ix_media_assets_profile_id", table_name="media_assets")
    op.drop_table("media_assets")

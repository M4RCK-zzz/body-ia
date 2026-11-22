"""Análisis de pose (Fase 5): tabla pose_analyses

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pose_analyses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "media_asset_id",
            sa.Uuid(),
            sa.ForeignKey("media_assets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("model_name", sa.String(64), nullable=True),
        sa.Column("model_version", sa.String(96), nullable=True),
        sa.Column("model_config", postgresql.JSONB(), nullable=True),
        sa.Column("landmarks_json", postgresql.JSONB(), nullable=True),
        sa.Column("quality_flags_json", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.String(300), nullable=True),
        sa.Column("created_by_snapshot", sa.String(120), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'needs_review')",
            name="ck_pose_analyses_status",
        ),
        sa.CheckConstraint(
            "(status IN ('completed', 'needs_review') AND landmarks_json IS NOT NULL) "
            "OR (status NOT IN ('completed', 'needs_review') AND landmarks_json IS NULL)",
            name="ck_pose_analyses_landmarks",
        ),
        sa.CheckConstraint(
            "(status = 'queued' AND started_at IS NULL AND completed_at IS NULL) "
            "OR (status = 'processing' AND started_at IS NOT NULL AND completed_at IS NULL) "
            "OR (status IN ('completed', 'needs_review', 'failed') "
            "AND started_at IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_pose_analyses_lifecycle",
        ),
    )
    op.create_index("ix_pose_analyses_media_asset_id", "pose_analyses", ["media_asset_id"])
    op.create_index("ix_pose_analyses_profile_created_at", "pose_analyses", ["profile_id", "created_at"])
    op.create_index("ix_pose_analyses_status_created_at", "pose_analyses", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_pose_analyses_status_created_at", table_name="pose_analyses")
    op.drop_index("ix_pose_analyses_profile_created_at", table_name="pose_analyses")
    op.drop_index("ix_pose_analyses_media_asset_id", table_name="pose_analyses")
    op.drop_table("pose_analyses")

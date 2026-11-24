"""profiles and measurements

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_code", sa.String(40), nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("display_code"),
        sa.CheckConstraint("status IN ('active', 'archived', 'restricted')", name="status_valid"),
    )

    op.create_table(
        "measurements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("metric_type", sa.String(32), nullable=False),
        sa.Column("value", sa.Numeric(7, 2), nullable=False),
        sa.Column("unit", sa.String(8), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("correction_reason", sa.String(300), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["measurements.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("supersedes_id"),
        sa.CheckConstraint("value > 0", name="value_positive"),
        sa.CheckConstraint(
            "(supersedes_id IS NULL) = (correction_reason IS NULL)", name="correction_has_reason"
        ),
    )
    op.create_index(
        "ix_measurements_profile_metric_time",
        "measurements",
        ["profile_id", "metric_type", "measured_at"],
    )

    op.execute(
        """
        CREATE FUNCTION prevent_measurement_update() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'measurements are immutable: create a correction instead'
                USING ERRCODE = 'restrict_violation';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_measurements_immutable
        BEFORE UPDATE ON measurements
        FOR EACH ROW EXECUTE FUNCTION prevent_measurement_update()
        """
    )

def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_measurements_immutable ON measurements")
    op.execute("DROP FUNCTION IF EXISTS prevent_measurement_update()")
    op.drop_index("ix_measurements_profile_metric_time", table_name="measurements")
    op.drop_table("measurements")
    op.drop_table("profiles")
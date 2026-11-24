"""Simulación de escenarios hipotéticos (Fase 8): simulations + simulation_baselines

Revision ID: 0008
Revises: 0007

Un escenario es SIEMPRE `data_kind='simulation'`. Esta migración **no toca la tabla
`measurements`**: sólo añade tablas nuevas, con FK `RESTRICT` a las mediciones usadas
como referencia base. El resultado del motor vive en JSONB (no hay binarios).

Triggers:
- `trg_simulations_protect`: un escenario completado/archivado no puede alterar su
  entrada, su base, su motor ni su resultado (sólo puede archivarse).
- `trg_simulations_no_delete`: los escenarios completados/archivados se archivan, no
  se eliminan.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "simulations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("data_kind", sa.String(16), nullable=False, server_default="simulation"),
        sa.Column("engine_name", sa.String(40), nullable=False),
        sa.Column("engine_version", sa.String(20), nullable=False),
        sa.Column(
            "engine_config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("parameters_json", postgresql.JSONB(), nullable=False),
        sa.Column("baseline_hash", sa.String(64), nullable=False),
        sa.Column("result_json", postgresql.JSONB(), nullable=True),
        sa.Column("result_checksum", sa.String(64), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("error_message", sa.String(300), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_by_snapshot", sa.String(120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "status IN ('draft', 'queued', 'completed', 'failed', 'archived')",
            name="ck_simulations_status",
        ),
        sa.CheckConstraint("data_kind = 'simulation'", name="ck_simulations_data_kind"),
        sa.CheckConstraint(
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
            name="ck_simulations_lifecycle",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(parameters_json) = 'object' AND parameters_json <> '{}'::jsonb",
            name="ck_simulations_parameters_shape",
        ),
        sa.CheckConstraint(
            "length(btrim(label)) BETWEEN 1 AND 80", name="ck_simulations_label_len"
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at",
            name="ck_simulations_timeline",
        ),
    )

    op.create_table(
        "simulation_baselines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "simulation_id",
            sa.Uuid(),
            sa.ForeignKey("simulations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("metric_type", sa.String(32), nullable=False),
        sa.Column(
            "measurement_id",
            sa.Uuid(),
            sa.ForeignKey("measurements.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("value_snapshot", sa.Numeric(7, 2), nullable=False),
        sa.Column("unit", sa.String(8), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("simulation_id", "metric_type", name="uq_simulation_metric"),
    )

    op.create_index(
        "ix_simulations_profile_created_at", "simulations", ["profile_id", "created_at"]
    )
    op.create_index(
        "ix_simulations_queue",
        "simulations",
        ["queued_at"],
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_index(
        "ix_simulations_creator", "simulations", ["created_by_user_id", "created_at"]
    )
    op.create_index(
        "ix_simulation_baselines_measurement", "simulation_baselines", ["measurement_id"]
    )

    op.execute(
        """
        CREATE FUNCTION protect_completed_simulation() RETURNS trigger AS $$
        BEGIN
            IF OLD.status IN ('completed', 'archived') THEN
                IF NEW.result_json IS DISTINCT FROM OLD.result_json
                   OR NEW.result_checksum IS DISTINCT FROM OLD.result_checksum
                   OR NEW.baseline_hash IS DISTINCT FROM OLD.baseline_hash
                   OR NEW.parameters_json IS DISTINCT FROM OLD.parameters_json
                   OR NEW.engine_name IS DISTINCT FROM OLD.engine_name
                   OR NEW.engine_version IS DISTINCT FROM OLD.engine_version
                   OR NEW.engine_config IS DISTINCT FROM OLD.engine_config
                   OR NEW.profile_id IS DISTINCT FROM OLD.profile_id THEN
                    RAISE EXCEPTION 'Un escenario completado no puede modificarse';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_simulations_protect
        BEFORE UPDATE ON simulations
        FOR EACH ROW EXECUTE FUNCTION protect_completed_simulation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION prevent_simulation_delete() RETURNS trigger AS $$
        BEGIN
            IF OLD.status IN ('completed', 'archived') THEN
                RAISE EXCEPTION 'Un escenario completado no se elimina: se archiva';
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_simulations_no_delete
        BEFORE DELETE ON simulations
        FOR EACH ROW EXECUTE FUNCTION prevent_simulation_delete();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_simulations_no_delete ON simulations")
    op.execute("DROP FUNCTION IF EXISTS prevent_simulation_delete()")
    op.execute("DROP TRIGGER IF EXISTS trg_simulations_protect ON simulations")
    op.execute("DROP FUNCTION IF EXISTS protect_completed_simulation()")
    op.drop_index("ix_simulation_baselines_measurement", table_name="simulation_baselines")
    op.drop_index("ix_simulations_creator", table_name="simulations")
    op.drop_index("ix_simulations_queue", table_name="simulations")
    op.drop_index("ix_simulations_profile_created_at", table_name="simulations")
    op.drop_table("simulation_baselines")
    op.drop_table("simulations")

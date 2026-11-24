"""worker heartbeats (Fase 9)

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeats",
        sa.Column("name", sa.String(length=40), primary_key=True),
        sa.Column("worker_version", sa.String(length=20), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("iterations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=300), nullable=True),
    )
    op.create_index(
        "ix_worker_heartbeats_last_seen_at", "worker_heartbeats", ["last_seen_at"]
    )
    # Un latido solo puede ir hacia adelante: si el reloj del worker retrocede,
    # se conserva el valor mayor (evita que un worker "resucite" al reiniciarse).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION worker_heartbeats_monotonic() RETURNS trigger AS $$
        BEGIN
            IF NEW.last_seen_at < OLD.last_seen_at THEN
                NEW.last_seen_at := OLD.last_seen_at;
            END IF;
            IF NEW.started_at < OLD.started_at THEN
                NEW.started_at := OLD.started_at;
            END IF;
            IF NEW.iterations < OLD.iterations THEN
                NEW.iterations := OLD.iterations;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_worker_heartbeats_monotonic
        BEFORE UPDATE ON worker_heartbeats
        FOR EACH ROW EXECUTE FUNCTION worker_heartbeats_monotonic();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_worker_heartbeats_monotonic ON worker_heartbeats")
    op.execute("DROP FUNCTION IF EXISTS worker_heartbeats_monotonic()")
    op.drop_index("ix_worker_heartbeats_last_seen_at", table_name="worker_heartbeats")
    op.drop_table("worker_heartbeats")

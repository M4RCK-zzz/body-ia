"""identidad (users, roles, user_roles) y auditoría append-only

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("name", sa.String(30), primary_key=True),
        sa.Column("description", sa.String(200), nullable=False),
    )
    op.bulk_insert(
        sa.table("roles", sa.column("name", sa.String), sa.column("description", sa.String)),
        [
            {
                "name": "admin",
                "description": (
                    "Administra cuentas y roles. "
                    "No accede a expedientes sin acceso explícito."
                ),
            },
            {
                "name": "professional",
                "description": "Gestiona expedientes de terceros cuando estos le conceden acceso.",
            },
            {"name": "user", "description": "Gestiona sus propios expedientes."},
        ],
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lower"),
    )

    op.create_table(
        "user_roles",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "role_name",
            sa.String(30),
            sa.ForeignKey("roles.name", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "actor_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("resource_type", sa.String(40), nullable=True),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("profile_id", sa.Uuid(), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_profile_id", "audit_events", ["profile_id"])

    op.execute(
        """
        CREATE FUNCTION prevent_audit_modification() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only'
                USING ERRCODE = 'restrict_violation';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_modification()")
    op.drop_table("audit_events")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
"""acceso por expediente, consentimientos, propietario y autor de mediciones

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = op.get_bind().execute(sa.text("SELECT count(*) FROM profiles")).scalar_one()
    if existing:
        raise RuntimeError(
            f"Migración 0004 abortada: hay {existing} expediente(s) de desarrollo sin propietario. "
            "No se asignan dueños de forma arbitraria. Ejecuta .\\scripts\\reset-dev-data.ps1 "
            "y vuelve a lanzar .\\scripts\\migrate.ps1."
        )

    op.add_column(
        "profiles",
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
    )
    op.create_index("ix_profiles_owner_id", "profiles", ["owner_id"])
    op.add_column(
        "measurements",
        sa.Column(
            "created_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )

    op.create_table(
        "profile_access",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column(
            "granted_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "revoked_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "level IN ('owner', 'editor', 'viewer')", name="ck_profile_access_level"
        ),
    )
    op.create_index(
        "uq_profile_access_active",
        "profile_access",
        ["profile_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "uq_profile_access_owner",
        "profile_access",
        ["profile_id"],
        unique=True,
        postgresql_where=sa.text("level = 'owner' AND revoked_at IS NULL"),
    )
    op.create_index("ix_profile_access_user_id", "profile_access", ["user_id"])

    op.create_table(
        "consents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column(
            "accepted_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "accepted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "revoked_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index(
        "uq_consents_active",
        "consents",
        ["profile_id", "purpose"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.execute(
        """
        CREATE FUNCTION protect_consent_rows() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'consents cannot be deleted' USING ERRCODE = 'restrict_violation';
            END IF;
            IF (NEW.id, NEW.profile_id, NEW.purpose, NEW.version, NEW.accepted_by, NEW.accepted_at)
               IS DISTINCT FROM
               (OLD.id, OLD.profile_id, OLD.purpose, OLD.version, OLD.accepted_by, OLD.accepted_at)
            THEN
                RAISE EXCEPTION 'consents are immutable: only revocation may change'
                    USING ERRCODE = 'restrict_violation';
            END IF;
            IF OLD.revoked_at IS NOT NULL
               AND (NEW.revoked_at IS DISTINCT FROM OLD.revoked_at
                    OR NEW.revoked_by IS DISTINCT FROM OLD.revoked_by)
            THEN
                RAISE EXCEPTION 'consent revocation is final' USING ERRCODE = 'restrict_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_consents_protect
        BEFORE UPDATE OR DELETE ON consents
        FOR EACH ROW EXECUTE FUNCTION protect_consent_rows();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_consents_protect ON consents")
    op.execute("DROP FUNCTION IF EXISTS protect_consent_rows()")
    op.drop_table("consents")
    op.drop_table("profile_access")
    op.drop_column("measurements", "created_by_user_id")
    op.drop_index("ix_profiles_owner_id", table_name="profiles")
    op.drop_column("profiles", "owner_id")
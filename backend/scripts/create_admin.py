"""Crea el primer administrador (o concede el rol admin a una cuenta existente)."""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import EmailStr, TypeAdapter, ValidationError  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.passwords import Argon2PasswordHasher  # noqa: E402
from app.domain.identity import AuditAction, RoleName, validate_password_strength  # noqa: E402
from app.repositories.sqlalchemy_audit_repository import SqlAlchemyAuditRepository  # noqa: E402
from app.repositories.sqlalchemy_user_repository import SqlAlchemyUserRepository  # noqa: E402
from app.services.audit_service import AuditRecorder  # noqa: E402


def main() -> int:
    raw_email = input("Correo del administrador: ").strip()
    try:
        email = str(TypeAdapter(EmailStr).validate_python(raw_email)).lower()
    except ValidationError:
        print("Correo no válido.")
        return 1

    engine = create_engine(get_settings().database_url)
    with Session(engine) as session:
        users = SqlAlchemyUserRepository(session)
        audit = AuditRecorder(SqlAlchemyAuditRepository(session))
        existing = users.get_by_email(email)

        if existing is not None:
            roles = sorted({*existing.role_names, RoleName.ADMIN.value})
            users.set_roles(existing, roles)
            user = existing
            print("La cuenta ya existía: se le concede el rol admin (contraseña sin cambios).")
        else:
            full_name = input("Nombre completo: ").strip()
            if len(full_name) < 2:
                print("Nombre demasiado corto.")
                return 1
            password = getpass.getpass("Contraseña: ")
            if password != getpass.getpass("Repite la contraseña: "):
                print("Las contraseñas no coinciden.")
                return 1
            try:
                validate_password_strength(password)
            except ValueError as exc:
                print(exc)
                return 1
            user = users.create(
                email=email,
                password_hash=Argon2PasswordHasher().hash(password),
                full_name=full_name,
                role_names=[RoleName.USER.value, RoleName.ADMIN.value],
            )

        audit.record(
            AuditAction.ADMIN_BOOTSTRAPPED,
            actor_id=None,
            resource_type="user",
            resource_id=str(user.id),
        )
        session.commit()
        print(f"Listo: {email} es administrador.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
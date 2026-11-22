from __future__ import annotations

from enum import StrEnum


class RoleName(StrEnum):
    ADMIN = "admin"
    PROFESSIONAL = "professional"
    USER = "user"


ROLE_DESCRIPTIONS: dict[RoleName, str] = {
    RoleName.ADMIN: "Administra cuentas y roles. No accede a expedientes sin acceso explícito.",
    RoleName.PROFESSIONAL: "Gestiona expedientes de terceros cuando estos le conceden acceso.",
    RoleName.USER: "Gestiona sus propios expedientes.",
}


class AuditAction(StrEnum):
    REGISTERED = "auth.registered"
    LOGIN = "auth.login"
    LOGIN_FAILED = "auth.login_failed"
    ACCOUNT_LOCKED = "auth.account_locked"
    ROLES_CHANGED = "admin.roles_changed"
    USER_ACTIVATED = "admin.user_activated"
    USER_DEACTIVATED = "admin.user_deactivated"
    ADMIN_BOOTSTRAPPED = "admin.bootstrapped"
    PROFILE_CREATED = "profile.created"
    PROFILE_RENAMED = "profile.renamed"
    PROFILE_ARCHIVED = "profile.archived"
    PROFILE_RESTORED = "profile.restored"
    MEASUREMENT_RECORDED = "measurement.recorded"
    MEASUREMENT_CORRECTED = "measurement.corrected"
    ACCESS_GRANTED = "access.granted"
    ACCESS_REVOKED = "access.revoked"
    ACCESS_DENIED = "access.denied"
    CONSENT_ACCEPTED = "consent.accepted"
    CONSENT_REVOKED = "consent.revoked"
    MEDIA_UPLOADED = "media.uploaded"
    MEDIA_REJECTED = "media.rejected"
    MEDIA_DELETED = "media.deleted"


MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128


def validate_password_strength(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"La contraseña no puede superar {MAX_PASSWORD_LENGTH} caracteres.")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise ValueError("La contraseña debe incluir al menos una letra y un número.")
    return password
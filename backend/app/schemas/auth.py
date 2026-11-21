from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domain.identity import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    RoleName,
    validate_password_strength,
)
from app.models.identity import User


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
    full_name: str = Field(min_length=2, max_length=120)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        return validate_password_strength(value)

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 2:
            raise ValueError("El nombre es demasiado corto.")
        return stripped


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    roles: list[RoleName]
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None

    @classmethod
    def from_user(cls, user: User) -> UserRead:
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            roles=[RoleName(r) for r in user.role_names],
            is_active=user.is_active,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )


class SessionRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead
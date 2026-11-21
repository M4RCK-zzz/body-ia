from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.domain.access import AccessLevel, ConsentPurpose
from app.models.access import Consent, ProfileAccess
from app.schemas.profile import ProfileRead


class ProfileDetailRead(ProfileRead):
    my_access: AccessLevel


class AccessGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    level: AccessLevel


class AccessRead(BaseModel):
    user_id: UUID
    email: str
    full_name: str
    level: AccessLevel
    granted_at: datetime

    @classmethod
    def from_access(cls, a: ProfileAccess) -> AccessRead:
        return cls(
            user_id=a.user_id,
            email=a.user.email,
            full_name=a.user.full_name,
            level=AccessLevel(a.level),
            granted_at=a.granted_at,
        )


class ConsentAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: ConsentPurpose
    declaration: Literal[True]


class ConsentRead(BaseModel):
    id: UUID
    purpose: ConsentPurpose
    version: str
    accepted_by: UUID
    accepted_at: datetime
    revoked_at: datetime | None

    @classmethod
    def from_consent(cls, c: Consent) -> ConsentRead:
        return cls(
            id=c.id,
            purpose=ConsentPurpose(c.purpose),
            version=c.version,
            accepted_by=c.accepted_by,
            accepted_at=c.accepted_at,
            revoked_at=c.revoked_at,
        )


class ConsentStatusRead(BaseModel):
    purpose: ConsentPurpose
    required_version: str
    valid: bool
    current: ConsentRead | None


class ConsentDocumentRead(BaseModel):
    purpose: ConsentPurpose
    version: str
    title: str
    paragraphs: list[str]
    declaration: str
    review_status: str
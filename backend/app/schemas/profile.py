import re
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator
from app.domain.profiles import ProfileStatus

_DISPLAY_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,39}$")

class ProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_code: str

    @field_validator("display_code")
    @classmethod
    def _normalize(cls, value: str) -> str:
        code = value.strip().upper()
        if not _DISPLAY_CODE.fullmatch(code):
            raise ValueError(
                "El código debe tener 3 a 40 caracteres: letras, números, guion o guion bajo."
            )
        return code

class ProfileUpdate(ProfileCreate):
    pass

class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    display_code: str
    status: ProfileStatus
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
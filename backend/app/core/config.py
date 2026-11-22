from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "BODYVISION AI"
    app_version: str = "0.1.0"
    environment: Literal["local", "staging", "production"] = "local"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str

    cors_origins: str = "http://localhost:5173"

    upload_dir: Path = BACKEND_DIR / "storage"
    max_upload_mb: int = Field(default=10, ge=1, le=50)
    media_retention_days: int = Field(default=365, ge=1, le=3650)
    media_max_pixels: int = Field(default=25_000_000, ge=1_000_000, le=100_000_000)
    pose_model_path: Path = BACKEND_DIR / "models" / "pose_landmarker_full.task"
    pose_poll_seconds: float = Field(default=5.0, ge=0.5, le=60.0)
    pose_stale_processing_seconds: int = Field(default=1800, ge=60, le=86400)
    pose_complete_threshold: int = Field(default=25, ge=5, le=33)
    pose_review_threshold: int = Field(default=10, ge=1, le=32)
    pose_visibility_threshold: float = Field(default=0.5, ge=0.1, le=1.0)

    # --- Identidad (Fase 3) ---
    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_issuer: str = "bodyvision-ai"
    access_token_minutes: int = Field(default=30, ge=5, le=1440)
    allow_registration: bool = True
    login_max_attempts: int = Field(default=5, ge=3, le=20)
    login_lock_minutes: int = Field(default=15, ge=1, le=1440)

    @field_validator("jwt_secret")
    @classmethod
    def _validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if len(secret) < 32:
            raise ValueError("JWT_SECRET debe tener al menos 32 caracteres.")
        if secret.lower().startswith("change-me"):
            raise ValueError("JWT_SECRET conserva el valor de ejemplo; genera uno real.")
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
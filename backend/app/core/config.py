from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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

    # --- Despliegue (Fase 9) ---
    domain: str = "bodyvision.example.com"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Documentación interactiva: se apaga sola en production salvo override explícito.
    enable_api_docs: bool | None = None
    # Cabeceras de seguridad y HSTS. HSTS solo tiene sentido con TLS real.
    security_headers: bool = True
    hsts_max_age: int = Field(default=31_536_000, ge=0, le=63_072_000)
    hsts_include_subdomains: bool = True
    # Orígenes permitidos para el visor/malla: nunca "*".
    trusted_proxies: str = ""

    # --- Rate limiting (Fase 9) ---
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = Field(default=600, ge=1, le=100_000)
    rate_limit_login_per_minute: int = Field(default=5, ge=1, le=1_000)
    rate_limit_login_per_hour: int = Field(default=20, ge=1, le=10_000)
    rate_limit_register_per_hour: int = Field(default=3, ge=1, le=1_000)
    rate_limit_worker_trigger_per_hour: int = Field(default=60, ge=1, le=10_000)
    rate_limit_download_per_hour: int = Field(default=120, ge=1, le=10_000)

    # --- Observabilidad (Fase 9) ---
    log_json: bool | None = None
    worker_stale_seconds: int = Field(default=120, ge=30, le=3600)

    database_url: str

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

    # --- Reportes (Fase 7) ---
    report_poll_seconds: float = Field(default=5.0, ge=0.5, le=60.0)
    report_stale_processing_seconds: int = Field(default=1800, ge=60, le=86400)

    # --- Retención y purga (Fase 9) ---
    report_retention_days: int = Field(default=365, ge=1, le=3650)
    simulation_retention_days: int = Field(default=365, ge=1, le=3650)
    retention_dry_run: bool = True
    retention_poll_seconds: float = Field(default=0.5, ge=0.0, le=60.0)

    # --- Simulación de escenarios (Fase 8) ---
    simulation_max_delta_percent: float = Field(default=30.0, ge=5.0, le=50.0)
    simulation_poll_seconds: float = Field(default=5.0, ge=0.5, le=60.0)
    simulation_stale_processing_seconds: int = Field(default=1800, ge=60, le=86400)
    simulation_max_active_per_profile: int = Field(default=20, ge=1, le=200)

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
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def docs_enabled(self) -> bool:
        """Staging/local: sí. Producción: solo con override explícito."""
        if self.enable_api_docs is not None:
            return self.enable_api_docs
        return not self.is_production

    @property
    def json_logs(self) -> bool:
        if self.log_json is not None:
            return self.log_json
        return self.environment != "local"

    @property
    def hsts_header(self) -> str | None:
        """HSTS solo con TLS y cabeceras activas; nunca en local sin TLS."""
        if not self.security_headers or self.environment == "local" or self.hsts_max_age <= 0:
            return None
        value = f"max-age={self.hsts_max_age}"
        if self.hsts_include_subdomains:
            value += "; includeSubDomains"
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        """Producción: falla al arrancar, no avisa por log.

        Un despliegue de producción con CORS abierto, documentación pública o
        secretos de ejemplo es un incidente esperando a ocurrir: se aborta.
        """
        if self.environment != "production":
            return self

        origins = self.cors_origins_list
        if not origins:
            raise ValueError("CORS_ORIGINS no puede estar vacío en production.")
        if "*" in origins:
            raise ValueError(
                "CORS_ORIGINS no admite '*' en production: indica los orígenes exactos."
            )
        if any(not origin.startswith("https://") for origin in origins):
            raise ValueError("CORS_ORIGINS debe usar https:// en production.")
        if self.debug:
            raise ValueError("DEBUG debe ser false en production.")
        if self.enable_api_docs is True:
            raise ValueError("ENABLE_API_DOCS no puede ser true en production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
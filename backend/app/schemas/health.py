from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = Field(description="'degraded' si alguna dependencia falla")
    service: str
    version: str
    environment: str
    database: Literal["up", "down"]
    timestamp: datetime


class ComponentStatus(BaseModel):
    name: Literal["database", "storage", "migrations"]
    ok: bool
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    ready: bool
    service: str
    version: str
    environment: str
    components: list[ComponentStatus]
    timestamp: datetime


class WorkerHealth(BaseModel):
    name: str
    version: str
    # `continuous=False` marca un worker one-shot (retención): su último latido se
    # informa, pero no participa del estado global ni del umbral de staleness.
    continuous: bool = True
    alive: bool
    last_seen_at: datetime
    age_seconds: int
    iterations: int
    last_error: str | None = None


class WorkersResponse(BaseModel):
    status: Literal["ok", "degraded", "unknown"]
    stale_after_seconds: int
    workers: list[WorkerHealth]
    timestamp: datetime

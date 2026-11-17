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
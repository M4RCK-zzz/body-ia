from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID
from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, PlainSerializer, field_validator,
)
from app.domain.enums import DataKind
from app.domain.measurements import MeasurementMethod, MeasurementType, MeasurementUnit

InputValue = Annotated[Decimal, Field(gt=0, max_digits=7, decimal_places=2)]
OutputValue = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]

def _blank_to_none(value: str | None) -> str | None:
    return value or None

class MeasurementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    metric_type: MeasurementType
    value: InputValue
    unit: MeasurementUnit
    measured_at: AwareDatetime
    method: MeasurementMethod
    
    notes: str | None = Field(default=None, max_length=500)

    _notes_blank = field_validator("notes")(_blank_to_none)

class MeasurementCorrect(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    value: InputValue
    measured_at: AwareDatetime | None = None
    method: MeasurementMethod | None = None
    
    reason: str = Field(min_length=3, max_length=300)
    notes: str | None = Field(default=None, max_length=500)

    _notes_blank = field_validator("notes")(_blank_to_none)

class MeasurementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    metric_type: MeasurementType
    value: OutputValue
    unit: MeasurementUnit
    measured_at: datetime
    method: MeasurementMethod
    created_by: str
    notes: str | None
    recorded_at: datetime
    supersedes_id: UUID | None
    correction_reason: str | None
    is_current: bool = True
    kind: DataKind = DataKind.OBSERVED

class SeriesPoint(BaseModel):
    id: UUID
    measured_at: datetime
    value: OutputValue
    method: MeasurementMethod
    corrected: bool

class MeasurementSeriesRead(BaseModel):
    metric_type: MeasurementType
    unit: MeasurementUnit
    kind: DataKind = DataKind.OBSERVED
    points: list[SeriesPoint]

class MetricSpecRead(BaseModel):
    metric_type: MeasurementType
    label: str
    unit: MeasurementUnit
    min_value: float
    max_value: float

class MethodRead(BaseModel):
    value: MeasurementMethod
    label: str

class MeasurementCatalogRead(BaseModel):
    metrics: list[MetricSpecRead]
    methods: list[MethodRead]
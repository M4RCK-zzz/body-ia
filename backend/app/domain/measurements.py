from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class MeasurementType(StrEnum):
    WEIGHT = "weight"
    HEIGHT = "height"
    WAIST = "waist"
    HIP = "hip"
    CHEST = "chest"
    ARM = "arm"
    THIGH = "thigh"

class MeasurementUnit(StrEnum):
    KG = "kg"
    CM = "cm"

class MeasurementMethod(StrEnum):
    MANUAL_TAPE = "manual_tape"
    SCALE = "scale"
    PROFESSIONAL = "professional"
    SELF_REPORTED = "self_reported"
    OTHER = "other"

@dataclass(frozen=True, slots=True)
class NewMeasurement:
    metric_type: MeasurementType
    value: Decimal
    unit: MeasurementUnit
    measured_at: datetime
    method: MeasurementMethod
    created_by: str
    notes: str | None = None

@dataclass(frozen=True, slots=True)
class MeasurementCorrection:
    value: Decimal
    created_by: str
    reason: str
    measured_at: datetime | None = None
    method: MeasurementMethod | None = None
    notes: str | None = None
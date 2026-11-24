from collections.abc import Iterable
from dataclasses import dataclass, replace
from decimal import Decimal

from app.domain.measurements import MeasurementMethod, MeasurementType, MeasurementUnit


@dataclass(frozen=True, slots=True)
class MetricSpec:
    metric_type: MeasurementType
    label: str
    unit: MeasurementUnit
    min_value: Decimal
    max_value: Decimal

    def contains(self, value: Decimal) -> bool:
        return self.min_value <= value <= self.max_value

METHOD_LABELS: dict[MeasurementMethod, str] = {
    MeasurementMethod.MANUAL_TAPE: "Cinta métrica manual",
    MeasurementMethod.SCALE: "Báscula",
    MeasurementMethod.PROFESSIONAL: "Profesional",
    MeasurementMethod.SELF_REPORTED: "Autorreporte",
    MeasurementMethod.OTHER: "Otro",
}

_DEFAULT_SPECS = (
    MetricSpec(MeasurementType.WEIGHT, "Peso", MeasurementUnit.KG, Decimal("2"), Decimal("500")),
    MetricSpec(
        MeasurementType.HEIGHT, "Estatura", MeasurementUnit.CM, Decimal("30"), Decimal("272")
    ),
    MetricSpec(MeasurementType.WAIST, "Cintura", MeasurementUnit.CM, Decimal("20"), Decimal("300")),
    MetricSpec(MeasurementType.HIP, "Cadera", MeasurementUnit.CM, Decimal("20"), Decimal("300")),
    MetricSpec(MeasurementType.CHEST, "Pecho", MeasurementUnit.CM, Decimal("20"), Decimal("300")),
    MetricSpec(MeasurementType.ARM, "Brazo", MeasurementUnit.CM, Decimal("5"), Decimal("100")),
    MetricSpec(MeasurementType.THIGH, "Muslo", MeasurementUnit.CM, Decimal("10"), Decimal("150")),
)

class MetricCatalog:
    def __init__(self, specs: Iterable[MetricSpec]) -> None:
        self._specs = {spec.metric_type: spec for spec in specs}

    def get(self, metric_type: MeasurementType) -> MetricSpec | None:
        return self._specs.get(metric_type)

    def all(self) -> list[MetricSpec]:
        return list(self._specs.values())

    def with_range(
        self, metric_type: MeasurementType, *, min_value: Decimal, max_value: Decimal
    ) -> "MetricCatalog":
        updated = dict(self._specs)
        updated[metric_type] = replace(
            self._specs[metric_type], min_value=min_value, max_value=max_value
        )
        return MetricCatalog(updated.values())

def default_catalog() -> MetricCatalog:
    return MetricCatalog(_DEFAULT_SPECS)
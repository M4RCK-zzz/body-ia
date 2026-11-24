from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.simulation import (
    ENGINE_NAME,
    ENGINE_VERSION,
    SCENARIO_WARNINGS,
    SIMULABLE_METRICS,
    SIMULATION_DISCLAIMER,
    BaselinePoint,
    EngineLimits,
    MetricParameter,
    SimulationError,
    apply_scenario,
    build_baseline,
    canonical_hash,
    parse_parameters,
    quantize,
    unit_for,
)

NOW = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)

CONTRACT = {
    "weight": ("2", "500"),
    "height": ("30", "272"),
    "waist": ("20", "300"),
    "hip": ("20", "300"),
    "chest": ("20", "300"),
    "arm": ("5", "100"),
    "thigh": ("10", "150"),
}


def _points(**values: str) -> list[BaselinePoint]:
    defaults = {
        "weight": "80.00",
        "height": "170.00",
        "waist": "88.00",
        "hip": "100.00",
    }
    defaults.update(values)
    return [
        BaselinePoint(metric, f"id-{metric}", Decimal(value), unit_for(metric), NOW)
        for metric, value in defaults.items()
    ]


def _limits(**overrides) -> EngineLimits:
    return EngineLimits(
        max_delta_percent=overrides.get("max_delta_percent", Decimal("30")),
        contract=CONTRACT,
    )


def _run(parameters, points=None, limits=None):
    baseline = build_baseline(points or _points())
    return apply_scenario(baseline, parameters, limits=limits or _limits())


class TestBaseline:
    def test_hash_is_order_independent(self):
        forward = build_baseline(_points())
        backward = build_baseline(list(reversed(_points())))
        assert forward.hash == backward.hash

    def test_hash_changes_with_value(self):
        assert build_baseline(_points()).hash != build_baseline(_points(waist="89.00")).hash

    def test_hash_is_sha256_hex(self):
        digest = build_baseline(_points()).hash
        assert len(digest) == 64
        assert int(digest, 16) >= 0


class TestScenarioArithmetic:
    def test_absolute_delta(self):
        result = _run([MetricParameter("waist", "delta_absolute", Decimal("-4.40"))])
        metric = result.as_dict()["metrics"]["waist"]

        assert metric["baseline"] == "88.00"
        assert metric["simulated"] == "83.60"
        assert metric["delta_absolute"] == "-4.40"
        assert metric["delta_percent"] == "-5.00"
        assert metric["clamped"] is False

    def test_percent_delta(self):
        result = _run([MetricParameter("weight", "delta_percent", Decimal("-5"))])
        metric = result.as_dict()["metrics"]["weight"]

        assert metric["simulated"] == "76.00"
        assert metric["delta_absolute"] == "-4.00"

    def test_target_value(self):
        result = _run([MetricParameter("weight", "target_value", Decimal("74.50"))])
        metric = result.as_dict()["metrics"]["weight"]

        assert metric["simulated"] == "74.50"
        assert metric["delta_absolute"] == "-5.50"

    def test_quantizes_to_two_decimals(self):
        result = _run([MetricParameter("waist", "delta_percent", Decimal("-3.333"))])
        simulated = Decimal(result.as_dict()["metrics"]["waist"]["simulated"])
        assert simulated == quantize(simulated)

    def test_rejects_delta_over_limit(self):
        with pytest.raises(SimulationError, match="supera ±30%"):
            _run([MetricParameter("weight", "delta_percent", Decimal("-45"))])

    def test_rejects_absolute_delta_over_limit(self):
        # 30% de 80 kg = 24 kg
        with pytest.raises(SimulationError):
            _run([MetricParameter("weight", "delta_absolute", Decimal("-30"))])

    def test_clamps_to_catalog_range_and_flags(self):
        points = _points(waist="21.00")
        result = _run(
            [MetricParameter("waist", "delta_absolute", Decimal("-5"))], points=points
        )
        metric = result.as_dict()["metrics"]["waist"]

        assert metric["clamped"] is True
        assert Decimal(metric["simulated"]) >= Decimal("20")

    def test_rejects_non_positive_result(self):
        points = _points(weight="2.10")
        with pytest.raises(SimulationError):
            _run(
                [MetricParameter("weight", "delta_absolute", Decimal("-2.10"))], points=points
            )

    def test_is_deterministic(self):
        params = [MetricParameter("waist", "delta_absolute", Decimal("-4.4"))]
        first, second = _run(params), _run(params)

        assert first.as_dict() == second.as_dict()
        assert first.checksum() == second.checksum()

    def test_checksum_changes_with_result(self):
        one = _run([MetricParameter("waist", "delta_absolute", Decimal("-4.4"))])
        two = _run([MetricParameter("waist", "delta_absolute", Decimal("-2.4"))])
        assert one.checksum() != two.checksum()

    def test_output_declares_simulation_kind_and_engine(self):
        payload = _run([MetricParameter("waist", "delta_absolute", Decimal("-4"))]).as_dict()

        assert payload["data_kind"] == "simulation"
        assert payload["engine"] == {"name": ENGINE_NAME, "version": ENGINE_VERSION}
        assert payload["warnings"] == list(SCENARIO_WARNINGS)
        assert "escenario_hipotetico" in payload["warnings"]

    def test_unchanged_metrics_are_listed(self):
        result = _run([MetricParameter("waist", "delta_absolute", Decimal("-4"))])

        assert "weight" in result.unchanged
        assert "waist" not in result.unchanged


class TestDerivedIndicators:
    def test_waist_height_and_waist_hip(self):
        result = _run([MetricParameter("waist", "delta_absolute", Decimal("-4.40"))])

        assert result.derived["waist_height"]["baseline"] == "0.52"
        assert result.derived["waist_height"]["simulated"] == "0.49"
        assert result.derived["waist_hip"]["baseline"] == "0.88"
        assert result.derived["waist_hip"]["simulated"] == "0.84"

    def test_derived_uses_baseline_when_component_not_simulated(self):
        result = _run([MetricParameter("weight", "delta_percent", Decimal("-5"))])

        assert result.derived["waist_height"]["baseline"] == "0.52"
        assert result.derived["waist_height"]["simulated"] == "0.52"
        assert result.derived["waist_height"]["delta_absolute"] == "0.00"

    def test_no_bmi(self):
        result = _run([MetricParameter("waist", "delta_absolute", Decimal("-4"))])
        assert "bmi" not in result.derived
        assert all("bmi" not in key for key in result.derived)


class TestParameterValidation:
    def test_rejects_height_as_parameter(self):
        assert "height" not in {metric.value for metric in SIMULABLE_METRICS}
        with pytest.raises(SimulationError, match="no es simulable"):
            parse_parameters([MetricParameter("height", "delta_absolute", Decimal("2"))])

    def test_rejects_unknown_mode(self):
        with pytest.raises(SimulationError, match="Modo"):
            parse_parameters([{"metric_type": "waist", "mode": "forecast", "value": "1"}])

    def test_rejects_duplicates(self):
        with pytest.raises(SimulationError, match="repetida"):
            parse_parameters(
                [
                    MetricParameter("waist", "delta_absolute", Decimal("1")),
                    MetricParameter("waist", "delta_percent", Decimal("1")),
                ]
            )

    def test_rejects_all_zero(self):
        with pytest.raises(SimulationError, match="cero"):
            parse_parameters([MetricParameter("waist", "delta_absolute", Decimal("0"))])

    def test_rejects_too_many_metrics(self):
        with pytest.raises(SimulationError):
            parse_parameters(
                [
                    MetricParameter("waist", "delta_absolute", Decimal("1")),
                    MetricParameter("hip", "delta_absolute", Decimal("1")),
                    MetricParameter("chest", "delta_absolute", Decimal("1")),
                    MetricParameter("arm", "delta_absolute", Decimal("1")),
                    MetricParameter("thigh", "delta_absolute", Decimal("1")),
                ]
            )

    def test_rejects_empty(self):
        with pytest.raises(SimulationError):
            parse_parameters([])

    def test_target_must_be_positive(self):
        with pytest.raises(SimulationError, match="mayor que cero"):
            parse_parameters([MetricParameter("waist", "target_value", Decimal("0"))])

    def test_missing_baseline_metric_is_explicit(self):
        with pytest.raises(SimulationError, match="No hay medición vigente"):
            _run([MetricParameter("chest", "delta_absolute", Decimal("-3"))])


class TestLimits:
    def test_rejects_out_of_range_limit(self):
        with pytest.raises(SimulationError):
            EngineLimits(max_delta_percent=Decimal("60"), contract=CONTRACT)

    def test_config_is_serializable_and_persisted_contract(self):
        config = _limits().as_config()

        assert config["max_delta_percent"] == "30"
        assert config["coupled_metrics"] is False
        assert config["rounding"] == "2_decimals_half_up"
        assert config["height_as_reference_only"] is True
        assert config["contract"]["waist"] == {"min": "20", "max": "300"}
        assert "bmi" not in " ".join(config["derived"])

    def test_config_hash_is_stable(self):
        assert canonical_hash(_limits().as_config()) == canonical_hash(_limits().as_config())

    def test_missing_contract_is_rejected(self):
        with pytest.raises(SimulationError, match="rango del catálogo"):
            _run(
                [MetricParameter("waist", "delta_absolute", Decimal("-4"))],
                limits=EngineLimits(contract={"weight": ("2", "500")}),
            )


def test_disclaimer_is_non_clinical():
    lowered = SIMULATION_DISCLAIMER.lower()
    assert "no describe el cuerpo real" in lowered
    assert "diagnóstico" in lowered
    assert "no modifica" in lowered

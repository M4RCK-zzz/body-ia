from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.measurements import MeasurementType
from app.domain.reports import (
    ALLOWED_WINDOWS,
    DISCLAIMER,
    ReportKind,
    SeriesObservation,
    detect_outliers,
    is_measurement_report,
    is_pose_report,
    summarize_series,
)
from app.services.report_renderers import ReportContext, render_report

UTC = UTC
BASE = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


def _obs(values: list[float], start: datetime = BASE) -> list[SeriesObservation]:
    return [
        SeriesObservation(measured_at=start + timedelta(days=index), value=Decimal(str(value)))
        for index, value in enumerate(values)
    ]


def _ctx(**overrides) -> ReportContext:
    ctx = ReportContext(
        report_id="r-1",
        profile_code="BV-001",
        data_kind="observed",
        requested_by="Ana Torres",
        requested_at=BASE,
        date_from=BASE,
        date_to=BASE + timedelta(days=30),
    )
    return replace(ctx, **overrides) if overrides else ctx


def _trend(values: list[float], *, corrected: int = 0):
    return summarize_series(
        metric_type="weight",
        label="Peso",
        unit="kg",
        observations=_obs(values),
        corrected_count=corrected,
    )


class TestSummary:
    def test_latest_delta_and_count(self):
        trend = _trend([72.0, 72.4, 72.1, 71.8, 72.2], corrected=2)

        assert trend.count == 5
        assert trend.corrected_count == 2
        assert trend.last_value == Decimal("72.20")
        assert trend.previous_value == Decimal("71.80")
        assert trend.delta_absolute == Decimal("0.40")
        assert trend.delta_percent == Decimal("0.56")

    def test_empty_series_has_no_values(self):
        trend = _trend([])

        assert trend.count == 0
        assert trend.has_data is False
        assert trend.last_value is None
        assert trend.delta_absolute is None
        assert trend.delta_percent is None
        # Nunca se rellena con 0: el vacío se representa como ausencia de dato.
        assert trend.min_value is None and trend.median_value is None

    def test_single_point_has_no_delta(self):
        trend = _trend([80.0])

        assert trend.last_value == Decimal("80.00")
        assert trend.previous_value is None
        assert trend.delta_absolute is None

    def test_decimal_values_are_quantized(self):
        trend = _trend([70.123456, 70.987654])

        assert trend.last_value == Decimal("70.99")
        assert trend.mean_value == Decimal("70.56")

    def test_percent_with_zero_baseline_is_none(self):
        trend = _trend([0.0, 5.0])
        # El catálogo no admite 0, pero el dominio debe ser defensivo.
        assert trend.delta_percent is None

    def test_outlier_is_flagged_not_removed(self):
        trend = _trend([72.0, 72.4, 72.1, 88.0, 71.8, 72.2])

        assert trend.count == 6
        assert trend.outlier_count == 1
        assert trend.outlier_timestamps == (BASE + timedelta(days=3),)
        # El outlier sigue dentro de las estadísticas: se marca, no se descarta.
        assert trend.max_value == Decimal("88.00")


class TestOutliers:
    def test_needs_three_points(self):
        assert detect_outliers([Decimal("1"), Decimal("999")]) == set()

    def test_zero_mad_disables_detection(self):
        assert detect_outliers([Decimal("5"), Decimal("5"), Decimal("5")]) == set()

    def test_marks_far_value(self):
        values = [Decimal("10"), Decimal("10.2"), Decimal("9.9"), Decimal("30")]
        assert detect_outliers(values) == {3}


class TestReportDomain:
    def test_kinds_split_by_data_kind(self):
        assert is_measurement_report("measurements_csv") is True
        assert is_measurement_report("pose_pdf") is False
        assert is_pose_report("pose_csv") is True
        assert is_pose_report("measurements_pdf") is False

    def test_windows(self):
        assert ALLOWED_WINDOWS == (7, 30, 90)

    def test_disclaimer_is_non_clinical(self):
        assert "no" in DISCLAIMER.lower()
        assert "clínic" in DISCLAIMER.lower() or "clinic" in DISCLAIMER.lower()


class TestRenderers:
    def test_measurements_csv_has_header_and_disclaimer(self):
        data, mime = render_report(
            kind="measurements_csv",
            context=_ctx(),
            series=[(_trend([72.0]), _obs([72.0]))],
        )

        text = data.decode("utf-8")
        assert mime.startswith("text/csv")
        assert text.startswith("# BODYVISION AI - Mediciones observadas")
        assert "# data_kind;observed" in text
        assert "RESUMEN DESCRIPTIVO" in text
        assert "Peso" in text

    def test_measurements_pdf_is_real_pdf(self):
        data, mime = render_report(
            kind="measurements_pdf",
            context=_ctx(),
            series=[(_trend([72.0, 72.4]), _obs([72.0, 72.4]))],
        )

        assert mime == "application/pdf"
        assert data.startswith(b"%PDF-")
        assert data.rstrip().endswith(b"%%EOF")
        assert len(data) > 1000

    def test_pose_csv_keeps_visual_estimate_label(self):
        pose = _fake_pose()
        data, mime = render_report(
            kind="pose_csv",
            context=_ctx(data_kind="visual_estimate"),
            analyses=[pose],
        )

        text = data.decode("utf-8")
        assert mime.startswith("text/csv")
        assert "visual_estimate" in text
        assert "estimaci" in text.lower()

    def test_pose_pdf_is_real_pdf(self):
        data, mime = render_report(
            kind="pose_pdf",
            context=_ctx(data_kind="visual_estimate"),
            analyses=[_fake_pose()],
        )

        assert mime == "application/pdf"
        assert data.startswith(b"%PDF-")
        assert data.rstrip().endswith(b"%%EOF")

    def test_empty_report_never_prints_zero_values(self):
        empty = summarize_series(
            metric_type="waist", label="Cintura", unit="cm", observations=[]
        )
        data, _ = render_report(kind="measurements_csv", context=_ctx(), series=[(empty, [])])
        row = next(line for line in data.decode().splitlines() if line.startswith("waist"))

        assert "Cintura" in row
        assert "0.00" not in row

    def test_render_ignores_payload_of_other_kind(self):
        # Un CSV de pose no emite filas de mediciones aunque se pasen por error.
        data, _ = render_report(
            kind="pose_csv",
            context=_ctx(data_kind="visual_estimate"),
            series=[(_trend([70.0]), _obs([70.0]))],
        )
        assert "weight" not in data.decode("utf-8")

    def test_unknown_kind_is_rejected(self):
        with pytest.raises(ValueError):
            render_report(kind="xlsx", context=_ctx())


@dataclass
class _FakePose:
    id: str = "00000000-0000-0000-0000-000000000001"
    status: str = "completed"
    created_at: datetime = BASE
    completed_at: datetime = BASE + timedelta(minutes=2)
    model_name: str = "pose_landmarker_full"
    model_version: str = "a1b2c3d4e5"
    quality_flags_json: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.quality_flags_json is None:
            self.quality_flags_json = {
                "quality": "good",
                "visible_landmarks": 28,
                "total_landmarks": 33,
            }


def _fake_pose() -> _FakePose:
    return _FakePose()


def test_report_kind_members():
    assert {kind.value for kind in ReportKind} == {
        "measurements_csv",
        "measurements_pdf",
        "pose_csv",
        "pose_pdf",
    }


def test_measurement_type_used_in_trend_is_known():
    trend = _trend([70.0])
    assert MeasurementType(trend.metric_type).value == "weight"

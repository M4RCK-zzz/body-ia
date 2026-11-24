"""Renderizadores de reportes: CSV y PDF (Fase 7).

Funciones puras (sin BD, sin I/O): reciben datos ya calculados y devuelven bytes.
Así se testean de forma determinista y el worker solo orquesta.

Separación por DataKind:
- Mediciones → `observed`. Es el único tipo que puede llevar valores numéricos
  comparables entre sí.
- Pose → `visual_estimate`. Nunca incluye valores de medición y declara el modelo.
"""
from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from fpdf import FPDF

from app.domain.reports import (
    DISCLAIMER,
    REPORT_FORMAT,
    MetricTrend,
    SeriesObservation,
    is_measurement_report,
)

GENERATOR = "BODYVISION AI · generador de reportes v1"
# fpdf2 con fuentes core solo codifica latin-1: el PDF usa una variante ASCII segura.
GENERATOR_PDF = "BODYVISION AI - generador de reportes v1"
_NO_LATIN1 = {"\u2014": "-", "\u2013": "-", "\u00b7": "|", "\u2026": "...", "\u2022": "*"}

_CSV_HEADER_MEASUREMENTS = [
    "metric_type",
    "metrica",
    "fecha",
    "valor",
    "unidad",
    "delta_abs_previo",
    "atipico",
    "data_kind",
]
_CSV_HEADER_TRENDS = [
    "metric_type",
    "metrica",
    "unidad",
    "n",
    "n_corregidos",
    "primera_fecha",
    "ultima_fecha",
    "ultimo_valor",
    "delta_abs",
    "delta_pct",
    "min",
    "max",
    "media",
    "mediana",
    "n_atipicos",
    "data_kind",
]


@dataclass(frozen=True, slots=True)
class ReportContext:
    """Metadatos congelados del reporte, impresos en la cabecera del documento."""

    report_id: str
    profile_code: str
    data_kind: str
    requested_by: str
    requested_at: datetime
    date_from: datetime | None
    date_to: datetime | None
    generator: str = GENERATOR


def _decimal_to_str(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{value:.2f}"


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


# --- CSV ---------------------------------------------------------------------


def render_measurements_csv(
    *,
    context: ReportContext,
    series: Sequence[tuple[MetricTrend, Sequence[SeriesObservation]]],
) -> bytes:
    """CSV con una fila por medición vigente + bloque final de resumen por métrica."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")

    writer.writerow(["# BODYVISION AI - Mediciones observadas"])
    writer.writerow(["# report_id", context.report_id])
    writer.writerow(["# expediente", context.profile_code])
    writer.writerow(["# data_kind", "observed"])
    writer.writerow(["# solicitado_por", context.requested_by])
    writer.writerow(["# solicitado_el", _iso(context.requested_at)])
    writer.writerow(["# periodo_desde", _iso(context.date_from)])
    writer.writerow(["# periodo_hasta", _iso(context.date_to)])
    writer.writerow(["# generador", context.generator])
    writer.writerow(["# aviso", DISCLAIMER])
    writer.writerow([])

    writer.writerow(_CSV_HEADER_MEASUREMENTS)
    for trend, observations in series:
        outlier_at = set(trend.outlier_timestamps)
        previous: Decimal | None = None
        for point in observations:
            delta = "" if previous is None else f"{point.value - previous:.2f}"
            writer.writerow(
                [
                    trend.metric_type,
                    trend.label,
                    _iso(point.measured_at),
                    _decimal_to_str(point.value),
                    trend.unit,
                    delta,
                    "si" if point.measured_at in outlier_at else "no",
                    "observed",
                ]
            )
            previous = point.value

    writer.writerow([])
    writer.writerow(["# RESUMEN DESCRIPTIVO (solo estadística descriptiva, sin proyecciones)"])
    writer.writerow(_CSV_HEADER_TRENDS)
    for trend, _observations in series:
        writer.writerow(
            [
                trend.metric_type,
                trend.label,
                trend.unit,
                trend.count,
                trend.corrected_count,
                _iso(trend.first_at),
                _iso(trend.last_at),
                _decimal_to_str(trend.last_value),
                _decimal_to_str(trend.delta_absolute),
                _decimal_to_str(trend.delta_percent),
                _decimal_to_str(trend.min_value),
                _decimal_to_str(trend.max_value),
                _decimal_to_str(trend.mean_value),
                _decimal_to_str(trend.median_value),
                trend.outlier_count,
                "observed",
            ]
        )

    return buffer.getvalue().encode("utf-8")


def render_pose_csv(*, context: ReportContext, analyses: Sequence) -> bytes:
    """CSV de estimaciones de pose. Nunca contiene columnas de medición."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")

    writer.writerow(["# BODYVISION AI - Estimaciones visuales de pose"])
    writer.writerow(["# report_id", context.report_id])
    writer.writerow(["# expediente", context.profile_code])
    writer.writerow(["# data_kind", "visual_estimate"])
    writer.writerow(["# advertencia", "No son mediciones clinicas ni geometria corporal"])
    writer.writerow(["# solicitado_por", context.requested_by])
    writer.writerow(["# solicitado_el", _iso(context.requested_at)])
    writer.writerow(["# generador", context.generator])
    writer.writerow(["# aviso", DISCLAIMER])
    writer.writerow([])
    writer.writerow(
        [
            "analysis_id",
            "estado",
            "creado",
            "completado",
            "modelo",
            "version_modelo",
            "calidad",
            "landmarks_visibles",
            "landmarks_total",
            "poses_detectados",
            "data_kind",
        ]
    )
    for analysis in analyses:
        flags = analysis.quality_flags_json or {}
        writer.writerow(
            [
                str(analysis.id),
                analysis.status,
                _iso(analysis.created_at),
                _iso(analysis.completed_at),
                analysis.model_name or "",
                analysis.model_version or "",
                flags.get("quality", ""),
                flags.get("visible_landmarks", ""),
                flags.get("total_landmarks", ""),
                flags.get("pose_count", ""),
                "visual_estimate",
            ]
        )
    return buffer.getvalue().encode("utf-8")


# --- PDF ---------------------------------------------------------------------


class _ReportPDF(FPDF):
    """PDF con pie de página fijo: aviso no clínico + numeración."""

    def __init__(self, *, title: str, context: ReportContext) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.report_title = title
        self.context = context
        self.set_auto_page_break(auto=True, margin=22)
        self.set_margins(left=14, top=14, right=14)
        self.set_title(title)
        self.set_author("BODYVISION AI")
        self.set_creator(GENERATOR_PDF)
        profile_code = _pdf_text(context.profile_code)
        self.set_subject(f"Reporte {_pdf_text(title)} - expediente {profile_code}")

    def header(self) -> None:  # noqa: N802 - API de fpdf2
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(20, 40, 70)
        self.cell(0, 8, "BODYVISION AI", new_x="LEFT", new_y="NEXT")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(60, 70, 90)
        self.cell(0, 6, self.report_title, new_x="LEFT", new_y="NEXT")
        self.set_draw_color(34, 211, 238)
        self.set_line_width(0.6)
        self.line(self.l_margin, self.get_y() + 1, self.w - self.r_margin, self.get_y() + 1)
        self.ln(4)

    def footer(self) -> None:  # noqa: N802 - API de fpdf2
        self.set_y(-18)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(110, 120, 135)
        self.multi_cell(0, 3.4, DISCLAIMER[:220], new_x="LEFT", new_y="NEXT")
        self.cell(0, 4, f"Página {self.page_no()}/{{nb}}", align="R")


def _pdf_text(value: object) -> str:
    """Normaliza a latin-1 (fuentes core de fpdf2) sin reventar la generación."""
    if value is None:
        return ""
    text = str(value)
    for source, target in _NO_LATIN1.items():
        text = text.replace(source, target)
    return text.encode("latin-1", "replace").decode("latin-1")


def _kv_block(pdf: _ReportPDF, rows: Sequence[tuple[str, str]]) -> None:
    pdf.set_font("Helvetica", "", 9)
    label_width = 42
    value_width = pdf.w - pdf.l_margin - pdf.r_margin - label_width
    for label, value in rows:
        pdf.set_text_color(90, 100, 120)
        pdf.cell(label_width, 5.5, label, new_x="RIGHT")
        pdf.set_text_color(25, 30, 45)
        pdf.multi_cell(value_width, 5.5, _pdf_text(value) or "-", new_x="LEFT", new_y="NEXT")


def _table(
    pdf: _ReportPDF,
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
    widths: Sequence[int],
) -> None:
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(235, 242, 252)
    pdf.set_text_color(30, 45, 70)
    for label, width in zip(header, widths, strict=True):
        pdf.cell(width, 6, label, border=1, fill=True)
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(30, 35, 50)
    for row in rows:
        for value, width in zip(row, widths, strict=True):
            pdf.cell(width, 5.5, str(value)[:40], border=1)
        pdf.ln(5.5)


def _empty_notice(pdf: _ReportPDF, message: str) -> None:
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(120, 90, 30)
    pdf.multi_cell(0, 5.5, message, new_x="LEFT", new_y="NEXT")


def render_measurements_pdf(
    *,
    context: ReportContext,
    series: Sequence[tuple[MetricTrend, Sequence[SeriesObservation]]],
) -> bytes:
    title = "Reporte de mediciones observadas"
    pdf = _ReportPDF(title=title, context=context)
    pdf.alias_nb_pages()
    pdf.add_page()

    _kv_block(
        pdf,
        [
            ("Expediente", context.profile_code),
            ("Tipo de dato", "OBSERVADO (mediciones registradas por personas)"),
            ("Solicitado por", context.requested_by),
            ("Solicitado el", _iso(context.requested_at)),
            ("Periodo desde", _iso(context.date_from)),
            ("Periodo hasta", _iso(context.date_to)),
            ("Reporte", context.report_id),
        ],
    )
    pdf.ln(3)

    if not any(trend.count for trend, _ in series):
        _empty_notice(
            pdf,
            "Sin mediciones en el periodo solicitado. No se generan valores ni promedios "
            "cuando no hay datos: el reporte se emite vacío de forma explícita.",
        )
        return bytes(pdf.output())

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(20, 40, 70)
    pdf.cell(0, 7, "Resumen descriptivo por metrica", new_x="LEFT", new_y="NEXT")
    _table(
        pdf,
        ["Metrica", "n", "Ultimo", "D. abs", "D. %", "Min", "Max", "Atipicos"],
        [
            [
                trend.label,
                str(trend.count),
                f"{_decimal_to_str(trend.last_value)} {trend.unit}".strip(),
                _decimal_to_str(trend.delta_absolute),
                _decimal_to_str(trend.delta_percent),
                _decimal_to_str(trend.min_value),
                _decimal_to_str(trend.max_value),
                str(trend.outlier_count),
            ]
            for trend, _ in series
            if trend.count
        ],
        [34, 12, 30, 22, 20, 20, 20, 20],
    )
    pdf.ln(4)
    _empty_notice(
        pdf,
        "Estadística descriptiva: último valor, delta, mínimo, máximo y atípicos por MAD. "
        "No hay interpolación, proyección ni interpretación clínica.",
    )

    for trend, observations in series:
        if not trend.count:
            continue
        if pdf.get_y() > 225:
            pdf.add_page()
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(20, 40, 70)
        pdf.cell(
            0,
            6,
            f"{_pdf_text(trend.label)} ({trend.unit}) | n={trend.count}",
            new_x="LEFT",
            new_y="NEXT",
        )
        outlier_at = set(trend.outlier_timestamps)
        rows = [
            [
                point.measured_at.strftime("%Y-%m-%d %H:%M"),
                _decimal_to_str(point.value),
                "sí" if point.measured_at in outlier_at else "",
            ]
            for point in observations[:200]
        ]
        _table(pdf, ["Fecha", "Valor", "Atipico"], rows, [70, 60, 28])
        if len(observations) > 200:
            _empty_notice(pdf, f"Se listan las primeras 200 de {len(observations)} mediciones.")

    return bytes(pdf.output())


def render_pose_pdf(*, context: ReportContext, analyses: Sequence) -> bytes:
    title = "Reporte de estimaciones visuales de pose"
    pdf = _ReportPDF(title=title, context=context)
    pdf.alias_nb_pages()
    pdf.add_page()

    _kv_block(
        pdf,
        [
            ("Expediente", context.profile_code),
            ("Tipo de dato", "ESTIMACIÓN VISUAL (no es medición clínica)"),
            ("Solicitado por", context.requested_by),
            ("Solicitado el", _iso(context.requested_at)),
            ("Periodo desde", _iso(context.date_from)),
            ("Periodo hasta", _iso(context.date_to)),
            ("Reporte", context.report_id),
        ],
    )
    pdf.ln(3)
    _empty_notice(
        pdf,
        "Los resultados de esta página provienen de un modelo de visión por computadora. "
        "Son referencias visuales orientativas: no representan geometría corporal, no miden "
        "y no deben mezclarse con las mediciones observadas de otros reportes.",
    )
    pdf.ln(2)

    if not analyses:
        _empty_notice(pdf, "Sin análisis de pose en el periodo solicitado.")
        return bytes(pdf.output())

    _table(
        pdf,
        ["Creado", "Estado", "Modelo", "Calidad", "Landmarks"],
        [
            [
                analysis.created_at.strftime("%Y-%m-%d %H:%M"),
                analysis.status,
                (analysis.model_version or "-")[:18],
                (analysis.quality_flags_json or {}).get("quality", "-"),
                (
                    f"{(analysis.quality_flags_json or {}).get('visible_landmarks', '-')}"
                    f"/{(analysis.quality_flags_json or {}).get('total_landmarks', '-')}"
                ),
            ]
            for analysis in analyses[:300]
        ],
        [38, 30, 40, 26, 26],
    )
    if len(analyses) > 300:
        _empty_notice(pdf, f"Se listan los primeros 300 de {len(analyses)} análisis.")

    return bytes(pdf.output())


def render_report(
    *,
    kind: str,
    context: ReportContext,
    series: Sequence[tuple[MetricTrend, Sequence[SeriesObservation]]] = (),
    analyses: Sequence = (),
) -> tuple[bytes, str]:
    """Devuelve (bytes, content_type) según el tipo de reporte."""
    try:
        fmt = REPORT_FORMAT[kind]
    except KeyError as exc:
        raise ValueError(f"Formato de reporte no soportado: {kind}") from exc
    if is_measurement_report(kind):
        if fmt == "csv":
            return (
                render_measurements_csv(context=context, series=series),
                "text/csv; charset=utf-8",
            )
        return render_measurements_pdf(context=context, series=series), "application/pdf"
    if fmt == "csv":
        return render_pose_csv(context=context, analyses=analyses), "text/csv; charset=utf-8"
    return render_pose_pdf(context=context, analyses=analyses), "application/pdf"

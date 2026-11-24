from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_report_service
from app.api.security import CurrentUser
from app.domain.reports import ReportStatus
from app.schemas.common import Page
from app.schemas.report import ReportRead, ReportRequest
from app.services.report_service import ReportService

router = APIRouter(prefix="/profiles/{profile_id}/reports", tags=["Reportes"])
asset_router = APIRouter(prefix="/reports", tags=["Reportes"])

_FILENAME_LABEL = {
    "measurements_csv": "mediciones",
    "measurements_pdf": "mediciones",
    "pose_csv": "pose",
    "pose_pdf": "pose",
}


def _read(report) -> ReportRead:
    data = ReportRead.model_validate(report)
    data.requested_by = report.requested_by_snapshot
    # El código vive en `parameters_json` (congelado al solicitar): se resuelve sin
    # tocar la base y sin depender de que el expediente se haya renombrado.
    data.profile_display_code = str(
        (report.parameters_json or {}).get("profile_code") or "—"
    )
    if report.status == ReportStatus.GENERATED.value:
        data.download_url = f"/api/reports/{report.id}/content"
    return data


@router.post(
    "",
    response_model=ReportRead,
    status_code=status.HTTP_201_CREATED,
    summary="Encola un reporte trazable (CSV/PDF) del expediente",
    description=(
        "Crea una tarea de generación asíncrona. Si ya existe un reporte idéntico "
        "en cola o en proceso, responde 200 con ese mismo reporte (idempotente). "
        "Los reportes de mediciones son OBSERVADO; los de pose, ESTIMACIÓN VISUAL: "
        "nunca se mezclan en el mismo documento."
    ),
)
def request_report(
    profile_id: UUID,
    payload: ReportRequest,
    user: CurrentUser,
    response: Response,
    service: ReportService = Depends(get_report_service),  # noqa: B008
) -> ReportRead:
    report, created = service.request(
        user,
        profile_id,
        kind=payload.kind,
        date_from=payload.date_from,
        date_to=payload.date_to,
        metric_types=payload.metrics,
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return _read(report)


@router.get("", response_model=Page[ReportRead])
def list_reports_for_profile(
    profile_id: UUID,
    user: CurrentUser,
    status_filter: ReportStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: ReportService = Depends(get_report_service),  # noqa: B008
) -> Page[ReportRead]:
    reports, total = service.list_for_profile(
        user,
        profile_id,
        status=status_filter.value if status_filter else None,
        limit=limit,
        offset=offset,
    )
    return Page[ReportRead](
        items=[_read(report) for report in reports], total=total, limit=limit, offset=offset
    )


@asset_router.get("", response_model=Page[ReportRead])
def list_my_reports(
    user: CurrentUser,
    status_filter: ReportStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: ReportService = Depends(get_report_service),  # noqa: B008
) -> Page[ReportRead]:
    """Reportes solicitados por el usuario, en expedientes donde su acceso sigue vivo."""
    reports, total = service.list_mine(
        user,
        status=status_filter.value if status_filter else None,
        limit=limit,
        offset=offset,
    )
    return Page[ReportRead](
        items=[_read(report) for report in reports], total=total, limit=limit, offset=offset
    )


@asset_router.get("/{report_id}", response_model=ReportRead)
def get_report(
    report_id: UUID,
    user: CurrentUser,
    service: ReportService = Depends(get_report_service),  # noqa: B008
) -> ReportRead:
    return _read(service.get(user, report_id))


@asset_router.get(
    "/{report_id}/content",
    response_class=Response,
    description=(
        "Descarga autenticada del reporte generado. Se verifica el checksum SHA-256 "
        "antes de servir el archivo y se audita cada descarga."
    ),
)
def download_report(
    report_id: UUID,
    user: CurrentUser,
    service: ReportService = Depends(get_report_service),  # noqa: B008
) -> Response:
    report, data = service.content(user, report_id)
    extension = report.format
    label = _FILENAME_LABEL.get(report.kind, "reporte")
    code = service.profile_code(report)
    filename = f"bodyvision_{label}_{code}_{report.id.hex[:8]}.{extension}"
    return Response(
        content=data,
        media_type=report.mime_type or "application/octet-stream",
        headers={
            "Content-Length": str(len(data)),
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Checksum-SHA256": report.checksum_sha256 or "",
        },
    )

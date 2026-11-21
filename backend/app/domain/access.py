from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AccessLevel(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


ACCESS_LABELS: dict[AccessLevel, str] = {
    AccessLevel.OWNER: "propietario",
    AccessLevel.EDITOR: "editor",
    AccessLevel.VIEWER: "lector",
}
_RANK = {AccessLevel.VIEWER: 1, AccessLevel.EDITOR: 2, AccessLevel.OWNER: 3}


def level_allows(actual: str, required: AccessLevel) -> bool:
    return _RANK[AccessLevel(actual)] >= _RANK[required]


class ConsentPurpose(StrEnum):
    DATA_PROCESSING = "data_processing"


@dataclass(frozen=True, slots=True)
class ConsentDocument:
    purpose: ConsentPurpose
    version: str
    title: str
    paragraphs: tuple[str, ...]
    declaration: str
    review_status: str


CONSENT_DOCUMENTS: dict[ConsentPurpose, ConsentDocument] = {
    ConsentPurpose.DATA_PROCESSING: ConsentDocument(
        purpose=ConsentPurpose.DATA_PROCESSING,
        version="2025-borrador-1",
        title="Consentimiento para el tratamiento de mediciones corporales",
        paragraphs=(
            "BODYVISION AI conserva en un historial las mediciones corporales que se "
            "introducen manualmente en este expediente.",
            "Los datos se usan solo para mostrar el historial y su evolución en la plataforma. "
            "La plataforma no emite diagnósticos ni recomendaciones médicas.",
            "Las simulaciones y estimaciones visuales son hipotéticas y no son mediciones reales.",
            "Solo pueden ver el expediente las personas a las que el propietario conceda acceso "
            "explícito. El propietario puede revocar accesos en cualquier momento.",
            "Puedes revocar este consentimiento: se bloquearán nuevos registros, pero el "
            "historial existente no se borra automáticamente.",
        ),
        declaration=(
            "Declaro que soy la persona a la que se refiere este expediente o que tengo "
            "autoridad para consentir en su nombre."
        ),
        review_status="Borrador pendiente de revisión legal (Ley 29733).",
    ),
}
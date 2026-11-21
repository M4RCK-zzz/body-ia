from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_consent_service
from app.api.security import CurrentUser
from app.domain.access import CONSENT_DOCUMENTS, ConsentPurpose
from app.schemas.access import (
    ConsentAcceptRequest,
    ConsentDocumentRead,
    ConsentRead,
    ConsentStatusRead,
)
from app.services.consent_service import ConsentService

router = APIRouter(tags=["Consentimiento"])

ServiceDep = Annotated[ConsentService, Depends(get_consent_service)]


@router.get("/consents/documents", response_model=list[ConsentDocumentRead])
def consent_documents(_user: CurrentUser) -> list[ConsentDocumentRead]:
    return [
        ConsentDocumentRead(
            purpose=d.purpose,
            version=d.version,
            title=d.title,
            paragraphs=list(d.paragraphs),
            declaration=d.declaration,
            review_status=d.review_status,
        )
        for d in CONSENT_DOCUMENTS.values()
    ]


@router.get("/profiles/{profile_id}/consents", response_model=list[ConsentStatusRead])
def consent_statuses(
    profile_id: UUID, user: CurrentUser, service: ServiceDep
) -> list[ConsentStatusRead]:
    return [
        ConsentStatusRead(
            purpose=s.purpose,
            required_version=s.required_version,
            valid=s.valid,
            current=ConsentRead.from_consent(s.current) if s.current else None,
        )
        for s in service.statuses(user, profile_id)
    ]


@router.post(
    "/profiles/{profile_id}/consents",
    response_model=ConsentRead,
    status_code=status.HTTP_201_CREATED,
)
def accept_consent(
    profile_id: UUID, payload: ConsentAcceptRequest, user: CurrentUser, service: ServiceDep
) -> ConsentRead:
    return ConsentRead.from_consent(service.accept(user, profile_id, payload.purpose))


@router.post("/profiles/{profile_id}/consents/{purpose}/revoke", response_model=ConsentRead)
def revoke_consent(
    profile_id: UUID, purpose: ConsentPurpose, user: CurrentUser, service: ServiceDep
) -> ConsentRead:
    return ConsentRead.from_consent(service.revoke(user, profile_id, purpose))
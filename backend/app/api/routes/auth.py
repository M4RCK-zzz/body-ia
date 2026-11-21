from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import get_auth_service
from app.api.security import CurrentUser
from app.schemas.auth import LoginRequest, RegisterRequest, SessionRead, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Autenticación"])

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, service: AuthServiceDep) -> UserRead:
    user = service.register(
        email=str(payload.email), password=payload.password, full_name=payload.full_name
    )
    return UserRead.from_user(user)


@router.post("/login", response_model=SessionRead)
def login(payload: LoginRequest, service: AuthServiceDep) -> SessionRead:
    result = service.login(email=payload.email, password=payload.password)
    return SessionRead(
        access_token=result.token.value,
        expires_in=result.token.expires_in,
        user=UserRead.from_user(result.user),
    )


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> UserRead:
    return UserRead.from_user(user)
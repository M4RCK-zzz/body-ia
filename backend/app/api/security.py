"""Dependencias de identidad y RBAC. En 3B se añade aquí el acceso por expediente."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import get_auth_service
from app.core.security_errors import AuthenticationError, PermissionDeniedError
from app.domain.identity import RoleName
from app.models.identity import User
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(auto_error=False, description="JWT obtenido en POST /api/auth/login")


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Falta el token de acceso.", code="missing_token")
    return service.authenticate(credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: RoleName):
    def checker(user: CurrentUser) -> User:
        if not user.has_any_role(roles):
            raise PermissionDeniedError("Tu rol no permite realizar esta acción.")
        return user

    return checker


require_admin = require_roles(RoleName.ADMIN)
AdminUser = Annotated[User, Depends(require_admin)]
from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.app.auth.tokens import AuthPrincipal, decode_access_token
from api.app.settings import Settings, get_settings
from api.app.tenant import set_client_id

_bearer = HTTPBearer(auto_error=False)


def get_current_principal(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthPrincipal:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(credentials.credentials, settings)


def require_platform_owner(
    principal: Annotated[AuthPrincipal, Depends(get_current_principal)],
) -> AuthPrincipal:
    """Platform admin routes only (Sprint 21)."""
    if not (principal.all_access or principal.role == "platform_owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform owner role required",
        )
    return principal


def require_tenant_access(
    principal: Annotated[AuthPrincipal, Depends(get_current_principal)],
    x_client_id: Annotated[Optional[str], Header(alias="X-Client-Id")] = None,
) -> AuthPrincipal:
    """Reject cross-tenant access. Platform owners may omit or pick any client."""
    if principal.all_access or principal.role == "platform_owner":
        if x_client_id:
            set_client_id(x_client_id)
        elif principal.tenant_id:
            set_client_id(principal.tenant_id)
        return principal

    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Org user has no tenant membership",
        )

    requested = (x_client_id or "").strip() or principal.tenant_id
    try:
        requested_norm = str(UUID(requested))
        allowed = str(UUID(principal.tenant_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant id",
        ) from exc

    if requested_norm != allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-tenant access denied",
        )

    set_client_id(allowed)
    return principal

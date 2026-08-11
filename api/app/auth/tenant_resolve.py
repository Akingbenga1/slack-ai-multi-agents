"""Shared HTTP tenant resolution for authenticated principals (Sprint 30.1)."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from api.app.auth.tokens import AuthPrincipal
from api.app.tenant import get_client_id


def resolve_tenant_for_principal(
    principal: AuthPrincipal,
    requested_id: Optional[str] = None,
    *,
    missing_detail: Optional[str] = None,
) -> str:
    """
    Resolve tenant ``client_id`` for an authenticated HTTP principal.

    Platform owners may use request context (``X-Client-Id``) or
    ``requested_id`` (body/form override). Org users are locked to JWT
    ``principal.tenant_id``; forged context / mismatched override → 403.

    Returns a normalized UUID string.
    """
    # Context may include client-controlled X-Client-Id; platform owners may
    # use it. Org users are locked to JWT membership (principal.tenant_id).
    from_ctx = get_client_id() or principal.tenant_id
    requested = (requested_id or "").strip() or None
    detail = missing_detail or (
        "tenant_id required (org user membership or X-Client-Id)"
    )

    if principal.all_access or principal.role == "platform_owner":
        chosen = requested or from_ctx
        if not chosen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail,
            )
        try:
            return str(UUID(chosen))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tenant id",
            ) from exc

    if not principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Org user has no tenant membership",
        )

    try:
        allowed = str(UUID(principal.tenant_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant id",
        ) from exc

    # Optional equality checks only — never elevate via forged X-Client-Id.
    for candidate, label in ((from_ctx, "context"), (requested, "request")):
        if not candidate:
            continue
        try:
            if str(UUID(candidate)) != allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cross-tenant access denied",
                )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tenant id ({label})",
            ) from exc

    return allowed


def resolve_tenant_uuid_for_principal(
    principal: AuthPrincipal,
    requested_id: Optional[str] = None,
    *,
    missing_detail: Optional[str] = None,
) -> UUID:
    """Same as ``resolve_tenant_for_principal`` but returns a ``UUID``."""
    return UUID(
        resolve_tenant_for_principal(
            principal,
            requested_id,
            missing_detail=missing_detail,
        )
    )

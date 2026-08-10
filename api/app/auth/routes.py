from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from api.app.auth.deps import get_current_principal, require_tenant_access
from api.app.auth.tokens import AuthPrincipal, RoleName, create_access_token
from api.app.db.models import Membership
from api.app.db.session import get_db
from api.app.membership import resolve_login_principal
from api.app.settings import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: RoleName
    tenant_id: Optional[str]
    all_access: bool


class MeResponse(BaseModel):
    sub: str
    email: str
    role: RoleName
    tenant_id: Optional[str]
    all_access: bool


class TenantPingResponse(BaseModel):
    ok: bool
    client_id: Optional[str]
    role: RoleName


@router.post("/token", response_model=TokenResponse)
def issue_token(
    body: TokenRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    principal = resolve_login_principal(db, email=body.email, password=body.password)
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(
        settings=settings,
        sub=principal.sub,
        email=principal.email,
        role=principal.role,
        tenant_id=principal.tenant_id,
    )
    return TokenResponse(
        access_token=token,
        role=principal.role,
        tenant_id=principal.tenant_id,
        all_access=principal.all_access,
    )


@router.get("/me", response_model=MeResponse)
def me(principal: Annotated[AuthPrincipal, Depends(get_current_principal)]) -> MeResponse:
    return MeResponse(
        sub=principal.sub,
        email=principal.email,
        role=principal.role,
        tenant_id=principal.tenant_id,
        all_access=principal.all_access,
    )


@router.get("/tenant-ping", response_model=TenantPingResponse)
def tenant_ping(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
) -> TenantPingResponse:
    """Protected probe used to verify cross-tenant rejection."""
    from api.app.tenant import get_client_id

    return TenantPingResponse(
        ok=True,
        client_id=get_client_id() or principal.tenant_id,
        role=principal.role,
    )


@router.get("/membership")
def membership_info(
    principal: Annotated[AuthPrincipal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Return membership wiring for the current user."""
    if principal.role == "platform_owner" or principal.all_access:
        return {
            "user_id": principal.sub,
            "role": principal.role,
            "all_access": True,
            "tenants": [],
            "note": "platform_owner has all-access; no single-tenant membership required",
        }

    user_id = UUID(principal.sub)
    rows = db.scalars(
        select(Membership)
        .options(joinedload(Membership.tenant), joinedload(Membership.role))
        .where(Membership.user_id == user_id)
    ).all()
    return {
        "user_id": principal.sub,
        "role": principal.role,
        "all_access": False,
        "tenants": [
            {
                "tenant_id": str(m.tenant_id),
                "tenant_slug": m.tenant.slug,
                "tenant_name": m.tenant.name,
                "role": m.role.name,
            }
            for m in rows
        ],
    }

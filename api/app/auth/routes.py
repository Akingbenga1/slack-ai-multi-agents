from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from api.app.admin.provision import OrganisationError
from api.app.auth.deps import get_current_principal, require_tenant_access
from api.app.auth.invites import (
    InviteError,
    accept_invite,
    create_invite,
    invite_public_row,
    list_invites,
    preview_invite,
)
from api.app.auth.provider import get_identity_provider
from api.app.auth.signup import register_organisation
from api.app.auth.tokens import AuthPrincipal, RoleName, create_access_token
from api.app.db.models import Membership
from api.app.db.session import get_db
from api.app.settings import Settings, get_settings
from api.app.tenant import get_client_id, set_client_id

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    slug: Optional[str] = Field(default=None, max_length=64)
    display_name: Optional[str] = Field(default=None, max_length=255)


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


class CreateInviteBody(BaseModel):
    email: EmailStr


class AcceptInviteBody(BaseModel):
    token: str = Field(min_length=8, max_length=256)
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=255)


def _organisation_http_error(exc: OrganisationError) -> HTTPException:
    msg = str(exc)
    code = (
        status.HTTP_409_CONFLICT
        if "already exists" in msg
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code=code, detail=msg)


def _invite_http_error(exc: InviteError) -> HTTPException:
    msg = str(exc)
    if "not found" in msg:
        code = status.HTTP_404_NOT_FOUND
    elif "already" in msg:
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=msg)


def _org_tenant_id(principal: AuthPrincipal) -> str:
    raw = get_client_id() or principal.tenant_id
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tenant required",
        )
    return str(UUID(raw))


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(
    body: SignupRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Public org registration — tenant + admin + session; no platform-owner ticket."""
    try:
        result = register_organisation(
            db,
            name=body.name,
            email=str(body.email),
            password=body.password,
            slug=body.slug,
            display_name=body.display_name,
            settings=settings,
        )
    except OrganisationError as exc:
        raise _organisation_http_error(exc) from exc

    org = result.organisation
    set_client_id(str(org.tenant.id))
    return {
        "access_token": result.access_token,
        "token_type": "bearer",
        "role": "org_admin",
        "tenant_id": str(org.tenant.id),
        "all_access": False,
        "tenant": {
            "id": str(org.tenant.id),
            "slug": org.tenant.slug,
            "name": org.tenant.name,
        },
        "admin": {
            "id": str(org.admin.id),
            "email": org.admin.email,
            "display_name": org.admin.display_name,
        },
    }


@router.post("/token", response_model=TokenResponse)
def issue_token(
    body: TokenRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Mint JWT after IdentityProvider.verify — IdP is selected by IDENTITY_PROVIDER."""
    idp = get_identity_provider(settings)
    principal = idp.verify(db, email=str(body.email), password=body.password)
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


@router.post("/invites", status_code=status.HTTP_201_CREATED)
def create_org_invite(
    body: CreateInviteBody,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Org admin creates a copyable magic-link invite (no SMTP)."""
    tenant_id = _org_tenant_id(principal)
    try:
        created = create_invite(
            db,
            tenant_id=tenant_id,
            email=str(body.email),
            actor_user_id=principal.sub,
            actor_email=principal.email,
            settings=settings,
        )
    except InviteError as exc:
        raise _invite_http_error(exc) from exc
    payload = invite_public_row(created.invite)
    payload["invite_url"] = created.invite_url
    payload["token"] = created.raw_token
    payload["note"] = (
        "Copy invite_url now. Email delivery is out of scope; token is not stored in plaintext."
    )
    return payload


@router.get("/invites")
def list_org_invites(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    tenant_id = _org_tenant_id(principal)
    rows = list_invites(db, tenant_id=tenant_id)
    return {"invites": [invite_public_row(r) for r in rows], "count": len(rows)}


@router.get("/invites/preview")
def preview_org_invite(
    token: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    try:
        return preview_invite(db, token=token, settings=settings)
    except InviteError as exc:
        raise _invite_http_error(exc) from exc


@router.post("/invites/accept", status_code=status.HTTP_201_CREATED)
def accept_org_invite(
    body: AcceptInviteBody,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Join the existing tenant. Does not create a second organisation."""
    try:
        accepted = accept_invite(
            db,
            token=body.token,
            password=body.password,
            display_name=body.display_name,
            settings=settings,
        )
    except InviteError as exc:
        raise _invite_http_error(exc) from exc
    set_client_id(str(accepted.tenant.id))
    return {
        "access_token": accepted.access_token,
        "token_type": "bearer",
        "role": "org_admin",
        "tenant_id": str(accepted.tenant.id),
        "all_access": False,
        "tenant": {
            "id": str(accepted.tenant.id),
            "slug": accepted.tenant.slug,
            "name": accepted.tenant.name,
        },
        "admin": {
            "id": str(accepted.user.id),
            "email": accepted.user.email,
            "display_name": accepted.user.display_name,
        },
    }

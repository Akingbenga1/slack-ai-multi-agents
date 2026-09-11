"""Platform-admin MCP server management for a tenant."""

from __future__ import annotations

from typing import Annotated, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.app.admin.actions import write_audit_log
from api.app.auth.deps import require_platform_owner
from api.app.auth.tokens import AuthPrincipal
from api.app.db.session import get_db
from api.app.mcp_servers.service import (
    McpInstallError,
    McpServerView,
    check_tenant_mcp_server,
    delete_tenant_mcp_server,
    get_tenant_mcp_server,
    install_tenant_mcp_server,
    list_tenant_mcp_servers,
    set_tenant_mcp_server_enabled,
    update_tenant_mcp_server,
)
from api.app.settings import Settings, get_settings
from api.app.tenant import set_client_id

router = APIRouter(tags=["admin-mcp-servers"])


class AdminMcpServerCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=2048)
    service_token: Optional[str] = Field(default=None, max_length=4096)
    enabled: bool = True
    verify: bool = True


class AdminMcpServerUpdateBody(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    url: Optional[str] = Field(default=None, min_length=1, max_length=2048)
    service_token: Optional[str] = Field(default=None, max_length=4096)
    clear_service_token: bool = False
    enabled: Optional[bool] = None
    verify: bool = True


class AdminMcpServerResponse(BaseModel):
    id: str
    name: str
    transport: str
    url: Optional[str] = None
    enabled: bool
    has_service_credential: bool
    has_oauth_credential: bool = False
    created_at: Optional[str] = None
    readiness: Optional[dict[str, Any]] = None


class AdminMcpServerListResponse(BaseModel):
    tenant_id: str
    servers: list[AdminMcpServerResponse]
    count: int


def _view_response(view: McpServerView) -> AdminMcpServerResponse:
    return AdminMcpServerResponse(
        id=view.id,
        name=view.name,
        transport=view.transport,
        url=view.url,
        enabled=view.enabled,
        has_service_credential=view.has_service_credential,
        has_oauth_credential=view.has_oauth_credential,
        created_at=view.created_at,
        readiness=view.readiness,
    )


def _raise_install_error(exc: McpInstallError) -> None:
    code = exc.code
    if code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if code == "duplicate_name":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/tenants/{tenant_id}/mcp-servers",
    response_model=AdminMcpServerListResponse,
)
def admin_list_tenant_mcp_servers(
    tenant_id: UUID,
    _: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminMcpServerListResponse:
    set_client_id(str(tenant_id))
    views = list_tenant_mcp_servers(db, tenant_id=tenant_id)
    return AdminMcpServerListResponse(
        tenant_id=str(tenant_id),
        servers=[_view_response(v) for v in views],
        count=len(views),
    )


@router.post(
    "/tenants/{tenant_id}/mcp-servers",
    response_model=AdminMcpServerResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_tenant_mcp_server(
    tenant_id: UUID,
    body: AdminMcpServerCreateBody,
    principal: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminMcpServerResponse:
    set_client_id(str(tenant_id))
    try:
        view = install_tenant_mcp_server(
            db,
            tenant_id=tenant_id,
            name=body.name,
            url=body.url,
            service_token=body.service_token,
            settings=settings,
            enabled=body.enabled,
            verify=body.verify,
        )
    except McpInstallError as exc:
        _raise_install_error(exc)
    write_audit_log(
        db,
        actor_user_id=principal.sub,
        actor_email=principal.email,
        action="mcp_server.create",
        tenant_id=tenant_id,
        detail={"server_id": view.id, "name": view.name},
    )
    db.commit()
    return _view_response(view)


@router.get(
    "/tenants/{tenant_id}/mcp-servers/{server_id}",
    response_model=AdminMcpServerResponse,
)
def admin_get_tenant_mcp_server(
    tenant_id: UUID,
    server_id: str,
    _: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminMcpServerResponse:
    set_client_id(str(tenant_id))
    view = get_tenant_mcp_server(db, tenant_id=tenant_id, server_id=server_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mcp server not found")
    return _view_response(view)


@router.patch(
    "/tenants/{tenant_id}/mcp-servers/{server_id}",
    response_model=AdminMcpServerResponse,
)
def admin_update_tenant_mcp_server(
    tenant_id: UUID,
    server_id: str,
    body: AdminMcpServerUpdateBody,
    principal: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminMcpServerResponse:
    set_client_id(str(tenant_id))
    try:
        view = update_tenant_mcp_server(
            db,
            tenant_id=tenant_id,
            server_id=server_id,
            settings=settings,
            name=body.name,
            url=body.url,
            service_token=body.service_token,
            clear_service_token=body.clear_service_token,
            enabled=body.enabled,
            verify=body.verify,
        )
    except McpInstallError as exc:
        _raise_install_error(exc)
    write_audit_log(
        db,
        actor_user_id=principal.sub,
        actor_email=principal.email,
        action="mcp_server.update",
        tenant_id=tenant_id,
        detail={"server_id": view.id, "name": view.name},
    )
    db.commit()
    return _view_response(view)


@router.delete(
    "/tenants/{tenant_id}/mcp-servers/{server_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def admin_delete_tenant_mcp_server(
    tenant_id: UUID,
    server_id: str,
    principal: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    set_client_id(str(tenant_id))
    if not delete_tenant_mcp_server(db, tenant_id=tenant_id, server_id=server_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mcp server not found")
    write_audit_log(
        db,
        actor_user_id=principal.sub,
        actor_email=principal.email,
        action="mcp_server.delete",
        tenant_id=tenant_id,
        detail={"server_id": server_id},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/tenants/{tenant_id}/mcp-servers/{server_id}/approve",
    response_model=AdminMcpServerResponse,
)
def admin_approve_tenant_mcp_server(
    tenant_id: UUID,
    server_id: str,
    principal: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminMcpServerResponse:
    set_client_id(str(tenant_id))
    try:
        view = set_tenant_mcp_server_enabled(
            db, tenant_id=tenant_id, server_id=server_id, enabled=True
        )
    except McpInstallError as exc:
        _raise_install_error(exc)
    write_audit_log(
        db,
        actor_user_id=principal.sub,
        actor_email=principal.email,
        action="mcp_server.approve",
        tenant_id=tenant_id,
        detail={"server_id": view.id, "name": view.name},
    )
    db.commit()
    return _view_response(view)


@router.post(
    "/tenants/{tenant_id}/mcp-servers/{server_id}/decline",
    response_model=AdminMcpServerResponse,
)
def admin_decline_tenant_mcp_server(
    tenant_id: UUID,
    server_id: str,
    principal: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminMcpServerResponse:
    set_client_id(str(tenant_id))
    try:
        view = set_tenant_mcp_server_enabled(
            db, tenant_id=tenant_id, server_id=server_id, enabled=False
        )
    except McpInstallError as exc:
        _raise_install_error(exc)
    write_audit_log(
        db,
        actor_user_id=principal.sub,
        actor_email=principal.email,
        action="mcp_server.decline",
        tenant_id=tenant_id,
        detail={"server_id": view.id, "name": view.name},
    )
    db.commit()
    return _view_response(view)


@router.post(
    "/tenants/{tenant_id}/mcp-servers/{server_id}/check",
    response_model=AdminMcpServerResponse,
)
def admin_check_tenant_mcp_server(
    tenant_id: UUID,
    server_id: str,
    _: Annotated[AuthPrincipal, Depends(require_platform_owner)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminMcpServerResponse:
    set_client_id(str(tenant_id))
    try:
        view = check_tenant_mcp_server(
            db, tenant_id=tenant_id, server_id=server_id, settings=settings
        )
    except McpInstallError as exc:
        _raise_install_error(exc)
    return _view_response(view)

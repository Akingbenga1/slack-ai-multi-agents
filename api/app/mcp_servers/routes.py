"""Tenant org-rep MCP server install APIs."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.app.auth.deps import require_tenant_access
from api.app.auth.tenant_resolve import resolve_tenant_uuid_for_principal
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
    update_tenant_mcp_server,
)
from api.app.settings import Settings, get_settings

router = APIRouter(prefix="/mcp-servers", tags=["mcp-servers"])


class McpServerCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=2048)
    service_token: Optional[str] = Field(default=None, max_length=4096)
    enabled: bool = True
    verify: bool = True


class McpServerUpdateBody(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    url: Optional[str] = Field(default=None, min_length=1, max_length=2048)
    service_token: Optional[str] = Field(default=None, max_length=4096)
    clear_service_token: bool = False
    enabled: Optional[bool] = None
    verify: bool = True


class McpServerResponse(BaseModel):
    id: str
    name: str
    transport: str
    url: Optional[str] = None
    enabled: bool
    has_service_credential: bool
    has_oauth_credential: bool = False
    created_at: Optional[str] = None
    readiness: Optional[dict[str, Any]] = None


class McpServerListResponse(BaseModel):
    servers: list[McpServerResponse]
    count: int


def _require_tenant(principal: AuthPrincipal):
    return resolve_tenant_uuid_for_principal(
        principal,
        missing_detail="tenant context required",
    )


def _view_response(view: McpServerView) -> McpServerResponse:
    return McpServerResponse(
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


@router.get("", response_model=McpServerListResponse)
def list_mcp_servers_api(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> McpServerListResponse:
    tid = _require_tenant(principal)
    views = list_tenant_mcp_servers(db, tenant_id=tid)
    return McpServerListResponse(
        servers=[_view_response(v) for v in views],
        count=len(views),
    )


@router.post("", response_model=McpServerResponse, status_code=status.HTTP_201_CREATED)
def create_mcp_server_api(
    body: McpServerCreateBody,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> McpServerResponse:
    tid = _require_tenant(principal)
    try:
        view = install_tenant_mcp_server(
            db,
            tenant_id=tid,
            name=body.name,
            url=body.url,
            service_token=body.service_token,
            settings=settings,
            enabled=body.enabled,
            verify=body.verify,
        )
    except McpInstallError as exc:
        _raise_install_error(exc)
    db.commit()
    return _view_response(view)


@router.get("/{server_id}", response_model=McpServerResponse)
def get_mcp_server_api(
    server_id: str,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> McpServerResponse:
    tid = _require_tenant(principal)
    view = get_tenant_mcp_server(db, tenant_id=tid, server_id=server_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mcp server not found")
    return _view_response(view)


@router.patch("/{server_id}", response_model=McpServerResponse)
def update_mcp_server_api(
    server_id: str,
    body: McpServerUpdateBody,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> McpServerResponse:
    tid = _require_tenant(principal)
    try:
        view = update_tenant_mcp_server(
            db,
            tenant_id=tid,
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
    db.commit()
    return _view_response(view)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mcp_server_api(
    server_id: str,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    tid = _require_tenant(principal)
    if not delete_tenant_mcp_server(db, tenant_id=tid, server_id=server_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mcp server not found")
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{server_id}/check", response_model=McpServerResponse)
def check_mcp_server_api(
    server_id: str,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> McpServerResponse:
    tid = _require_tenant(principal)
    try:
        view = check_tenant_mcp_server(
            db, tenant_id=tid, server_id=server_id, settings=settings
        )
    except McpInstallError as exc:
        _raise_install_error(exc)
    db.commit()
    return _view_response(view)


class McpOAuthStartResponse(BaseModel):
    server_id: str
    authorization_url: str
    state: str


@router.post("/{server_id}/oauth/start", response_model=McpOAuthStartResponse)
def start_mcp_oauth_api(
    server_id: str,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> McpOAuthStartResponse:
    from api.app.mcp_servers.oauth import McpOAuthError, start_mcp_oauth

    tid = _require_tenant(principal)
    try:
        started = start_mcp_oauth(
            db, tenant_id=tid, server_id=server_id, settings=settings
        )
    except McpOAuthError as exc:
        code = exc.code
        if code == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return McpOAuthStartResponse(
        server_id=started.server_id,
        authorization_url=started.authorization_url,
        state=started.state,
    )


@router.get("/oauth/callback")
def mcp_oauth_callback_api(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> Response:
    """OAuth redirect target — completes Connect and returns a simple HTML result."""
    from api.app.mcp_servers.oauth import McpOAuthError, complete_mcp_oauth

    if error:
        body = f"<html><body><h1>MCP Connect failed</h1><p>{error}</p></body></html>"
        return Response(content=body, media_type="text/html", status_code=400)
    if not code or not state:
        body = "<html><body><h1>MCP Connect failed</h1><p>Missing code or state.</p></body></html>"
        return Response(content=body, media_type="text/html", status_code=400)
    try:
        row = complete_mcp_oauth(db, state=state, code=code, settings=settings)
        db.commit()
    except McpOAuthError as exc:
        body = f"<html><body><h1>MCP Connect failed</h1><p>{exc}</p></body></html>"
        return Response(content=body, media_type="text/html", status_code=400)
    body = (
        "<html><body><h1>MCP Connect complete</h1>"
        f"<p>Server <strong>{row.name}</strong> is connected. You can close this window.</p>"
        "</body></html>"
    )
    return Response(content=body, media_type="text/html")

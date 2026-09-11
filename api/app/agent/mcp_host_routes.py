"""Control-plane API: list / check MCP servers for readiness.

Separate from the executor. Orchestrator never calls these routes.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.app.agent.mcp_host import (
    check_bundled_mcp,
    check_mcp_server,
    extract_http_url,
    extract_stdio_launch,
)
from api.app.auth.deps import require_tenant_access
from api.app.auth.tenant_resolve import resolve_tenant_uuid_for_principal
from api.app.auth.tokens import AuthPrincipal
from api.app.db.session import get_db
from api.app.db.tool_store import (
    get_mcp_server_by_name,
    list_mcp_servers,
    list_tool_registry,
    update_mcp_server,
)
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings

logger = get_logger("api.agent.mcp_host_routes")

# Prefix is intentionally NOT under /tools/{tool_name}.
router = APIRouter(prefix="/mcp-host", tags=["mcp-host"])


class McpHostServerRow(BaseModel):
    id: str
    name: str
    transport: str
    enabled: bool
    endpoint_hint: Optional[str] = None
    linked_tools: list[str] = Field(default_factory=list)
    created_at: Optional[str] = None


class McpHostListResponse(BaseModel):
    servers: list[McpHostServerRow]
    bundled: McpHostServerRow
    check_timeout_seconds: float


class McpHostCheckResponse(BaseModel):
    server_name: str
    transport: str
    ready: bool
    enabled: bool
    endpoint: Optional[str] = None
    tool_count: Optional[int] = None
    tool_names: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    detail: Optional[str] = None


class McpHostEnableUpdate(BaseModel):
    enabled: bool


def _require_client_uuid(principal: AuthPrincipal):
    return resolve_tenant_uuid_for_principal(
        principal,
        missing_detail="tenant context required",
    )


def _endpoint_hint(transport: str, config: dict[str, Any] | None) -> str | None:
    transport_norm = (transport or "").strip().lower()
    if transport_norm in {"http", "streamable-http", "sse", "websocket"}:
        return extract_http_url(config)
    if transport_norm in {"stdio", "std-io", "standard-io"}:
        launch = extract_stdio_launch(config)
        if launch is None:
            return None
        command, args, _env = launch
        return " ".join([command, *args]).strip() or command
    return None


def _linked_tools_by_server(
    db: Session,
    *,
    tenant_id: str,
) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for tool in list_tool_registry(db, tenant_id=tenant_id):
        if tool.kind != "mcp" or tool.mcp_server_id is None:
            continue
        key = str(tool.mcp_server_id)
        mapping.setdefault(key, []).append(tool.name)
    for names in mapping.values():
        names.sort(key=str.lower)
    return mapping


def _row_from_server(
    server: Any,
    *,
    linked: list[str],
) -> McpHostServerRow:
    cfg = server.connection_config if isinstance(server.connection_config, dict) else None
    return McpHostServerRow(
        id=str(server.id),
        name=server.name,
        transport=server.transport,
        enabled=bool(server.enabled),
        endpoint_hint=_endpoint_hint(server.transport, cfg),
        linked_tools=linked,
        created_at=str(server.created_at) if server.created_at else None,
    )


@router.get("", response_model=McpHostListResponse)
def list_mcp_host_servers(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> McpHostListResponse:
    """List registered MCP servers for the tenant (readiness control plane)."""
    tid = _require_client_uuid(principal)
    linked_map = _linked_tools_by_server(db, tenant_id=str(tid))
    servers = [
        _row_from_server(row, linked=linked_map.get(str(row.id), []))
        for row in list_mcp_servers(db, tenant_id=str(tid))
    ]
    servers.sort(key=lambda s: s.name.lower())
    return McpHostListResponse(
        servers=servers,
        bundled=McpHostServerRow(
            id="__bundled__",
            name="Bundled agent MCP",
            transport="bundled",
            enabled=True,
            endpoint_hint="in-process / settings stdio",
            linked_tools=[],
            created_at=None,
        ),
        check_timeout_seconds=float(settings.mcp_host_check_timeout_seconds),
    )


@router.post("/bundled/check", response_model=McpHostCheckResponse)
def check_mcp_host_bundled(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> McpHostCheckResponse:
    """Probe the bundled agent MCP (in-process or settings stdio)."""
    _require_client_uuid(principal)
    result = check_bundled_mcp(
        timeout_seconds=float(settings.mcp_host_check_timeout_seconds),
    )
    logger.info(
        "mcp_host_bundled_check ready=%s tools=%s",
        result.ready,
        result.tool_count,
    )
    return McpHostCheckResponse(
        server_name=result.server_name,
        transport=result.transport,
        ready=result.ready,
        enabled=result.enabled,
        endpoint=result.endpoint,
        tool_count=result.tool_count,
        tool_names=result.tool_names,
        error=result.error,
        detail=result.detail,
    )


@router.post("/{server_name}/check", response_model=McpHostCheckResponse)
def check_mcp_host_server(
    server_name: str,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> McpHostCheckResponse:
    """Probe one registered MCP server for initialize + list_tools readiness."""
    tid = _require_client_uuid(principal)
    row = get_mcp_server_by_name(db, tenant_id=str(tid), name=server_name)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mcp server not found")
    cfg = row.connection_config if isinstance(row.connection_config, dict) else None
    from api.app.db.tool_store import decrypt_mcp_server_secret

    result = check_mcp_server(
        server_name=row.name,
        transport=row.transport,
        connection_config=cfg,
        enabled=bool(row.enabled),
        timeout_seconds=float(settings.mcp_host_check_timeout_seconds),
        service_token=decrypt_mcp_server_secret(row, settings),
    )
    logger.info(
        "mcp_host_check server=%s ready=%s endpoint=%s",
        result.server_name,
        result.ready,
        result.endpoint,
    )
    return McpHostCheckResponse(
        server_name=result.server_name,
        transport=result.transport,
        ready=result.ready,
        enabled=result.enabled,
        endpoint=result.endpoint,
        tool_count=result.tool_count,
        tool_names=result.tool_names,
        error=result.error,
        detail=result.detail,
    )


@router.patch("/{server_name}", response_model=McpHostServerRow)
def update_mcp_host_server(
    server_name: str,
    body: McpHostEnableUpdate,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> McpHostServerRow:
    """Enable or disable a registered MCP server."""
    tid = _require_client_uuid(principal)
    updated = update_mcp_server(
        db,
        tenant_id=str(tid),
        name=server_name,
        enabled=body.enabled,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mcp server not found")
    db.commit()
    linked_map = _linked_tools_by_server(db, tenant_id=str(tid))
    logger.info(
        "mcp_host_enabled_updated server=%s enabled=%s",
        updated.name,
        updated.enabled,
    )
    return _row_from_server(updated, linked=linked_map.get(str(updated.id), []))

"""CRUD API for the tool_registry table (tenant-scoped).

All tools the orchestrator/executor can discover live in the DB.
No hardcoded tool sets — adding or removing a tool is a DB operation.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.app.auth.deps import require_tenant_access
from api.app.auth.tenant_resolve import resolve_tenant_uuid_for_principal
from api.app.auth.tokens import AuthPrincipal
from api.app.db.tool_store import (
    delete_tool_registry,
    get_mcp_server_by_name,
    get_tool_registry,
    insert_mcp_server,
    insert_tool_registry,
    list_tool_registry,
    update_tool_registry,
)
from api.app.db.session import get_db
from api.app.logging_config import get_logger

logger = get_logger("api.agent.tool_routes")

router = APIRouter(prefix="/tools", tags=["tools"])


class McpServerCreatePayload(BaseModel):
    """Optional nested payload so Create can register server + tool together."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    transport: str = Field(default="http", min_length=1, max_length=32)
    connection_config: Optional[dict[str, Any]] = None
    enabled: bool = True


class ToolCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    kind: str = Field(..., pattern=r"^(mcp|cli|http|code)$")
    description: Optional[str] = None
    mcp_server_id: Optional[UUID] = None
    config: Optional[dict[str, Any]] = None
    # When kind=mcp, create/reuse an mcp_servers row in the same request.
    mcp_server: Optional[McpServerCreatePayload] = None


class ToolUpdate(BaseModel):
    description: Optional[str] = None
    kind: Optional[str] = Field(default=None, pattern=r"^(mcp|cli|http|code)$")
    config: Optional[dict[str, Any]] = None


class ToolResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    kind: str
    description: Optional[str] = None
    mcp_server_id: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None


def _require_client_uuid(principal: AuthPrincipal) -> UUID:
    return resolve_tenant_uuid_for_principal(
        principal, missing_detail="tenant context required",
    )


def _to_response(row: Any) -> ToolResponse:
    return ToolResponse(
        id=str(row.id),
        tenant_id=str(row.tenant_id),
        name=row.name,
        kind=row.kind,
        description=row.description,
        mcp_server_id=str(row.mcp_server_id) if row.mcp_server_id else None,
        config=row.config if isinstance(row.config, dict) else None,
        created_at=str(row.created_at) if row.created_at else None,
    )


@router.get("", response_model=list[ToolResponse])
def list_tools(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ToolResponse]:
    """List all registered tools for the tenant."""
    tid = _require_client_uuid(principal)
    rows = list_tool_registry(db, tenant_id=str(tid))
    return [_to_response(r) for r in rows]


@router.get("/{tool_name}", response_model=ToolResponse)
def get_tool(
    tool_name: str,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> ToolResponse:
    """Get a single tool by name for the tenant."""
    tid = _require_client_uuid(principal)
    row = get_tool_registry(db, tenant_id=str(tid), name=tool_name)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tool not found")
    return _to_response(row)


def _normalize_mcp_transport(raw: str) -> str:
    t = (raw or "").strip().lower()
    if t in {"http", "streamable-http", "sse", "websocket"}:
        return "http"
    if t in {"stdio", "std-io", "standard-io"}:
        return "stdio"
    return t or "http"


@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
def create_tool(
    body: ToolCreate,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> ToolResponse:
    """Register a new tool for the tenant.

    For ``kind=mcp``, callers may pass ``mcp_server`` to create/reuse the
    linked ``mcp_servers`` row in the same transaction.
    """
    tid = _require_client_uuid(principal)
    existing = get_tool_registry(db, tenant_id=str(tid), name=body.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"tool {body.name!r} already exists",
        )

    mcp_server_id = body.mcp_server_id
    if body.kind == "mcp" and body.mcp_server is not None:
        server_name = (body.mcp_server.name or body.name).strip()
        if not server_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="mcp_server.name is required when creating an MCP tool",
            )
        transport = _normalize_mcp_transport(body.mcp_server.transport)
        server = get_mcp_server_by_name(db, tenant_id=str(tid), name=server_name)
        if server is None:
            server = insert_mcp_server(
                db,
                tenant_id=str(tid),
                name=server_name,
                transport=transport,
                connection_config=body.mcp_server.connection_config,
                enabled=body.mcp_server.enabled,
            )
        mcp_server_id = server.id
    elif body.kind == "mcp" and mcp_server_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="mcp tools require mcp_server_id or mcp_server payload",
        )

    row = insert_tool_registry(
        db,
        tenant_id=str(tid),
        name=body.name,
        kind=body.kind,
        description=body.description,
        mcp_server_id=mcp_server_id,
        config=body.config,
    )
    db.commit()
    return _to_response(row)


@router.patch("/{tool_name}", response_model=ToolResponse)
def update_tool(
    tool_name: str,
    body: ToolUpdate,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> ToolResponse:
    """Update a tool's metadata."""
    tid = _require_client_uuid(principal)
    row = update_tool_registry(
        db,
        tenant_id=str(tid),
        name=tool_name,
        description=body.description,
        kind=body.kind,
        config=body.config,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tool not found")
    db.commit()
    return _to_response(row)


@router.delete("/{tool_name}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_tool(
    tool_name: str,
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Remove a tool from the tenant's registry."""
    tid = _require_client_uuid(principal)
    deleted = delete_tool_registry(db, tenant_id=str(tid), name=tool_name)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tool not found")
    db.commit()


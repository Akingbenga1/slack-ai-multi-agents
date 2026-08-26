"""Tenant-scoped tool_registry and mcp_servers CRUD.

All MCP tool discovery is DB-driven. Adding or removing a tool is a
database operation — no hardcoded tool sets.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db.models import McpServer, ToolRegistry
from api.app.settings import Settings
from api.app.slack.crypto import decrypt_bot_token, encrypt_bot_token
from api.app.tenant import ClientIdRequired
from api.app.tenant import require_client_id as _require_client_id

MSG_NO_TENANT = "tenant_id is required"
_UNSET = object()


class TenantIdRequired(ClientIdRequired):
    """Raised when a store helper is missing tenant_id."""


def require_tenant_id(tenant_id: str | UUID | None, *, where: str = "tool store") -> str:
    raw = str(tenant_id).strip() if tenant_id is not None else ""
    try:
        return _require_client_id(raw or None, where=where, message=MSG_NO_TENANT)
    except ClientIdRequired as exc:
        if isinstance(exc, TenantIdRequired):
            raise
        raise TenantIdRequired(MSG_NO_TENANT) from exc


def _tenant_uuid(tenant_id: str | UUID | None, *, where: str) -> UUID:
    return UUID(require_tenant_id(tenant_id, where=where))


# ── MCP servers ──


def insert_mcp_server(
    db: Session,
    *,
    tenant_id: str | UUID | None,
    name: str,
    transport: str,
    connection_config: dict[str, Any] | None = None,
    enabled: bool = True,
) -> McpServer:
    tid = _tenant_uuid(tenant_id, where="insert_mcp_server")
    row = McpServer(
        tenant_id=tid,
        name=name,
        transport=transport,
        connection_config=connection_config,
        enabled=enabled,
    )
    db.add(row)
    db.flush()
    return row


def list_mcp_servers(db: Session, *, tenant_id: str | UUID | None) -> list[McpServer]:
    tid = _tenant_uuid(tenant_id, where="list_mcp_servers")
    return list(db.scalars(select(McpServer).where(McpServer.tenant_id == tid)).all())


def get_mcp_server_by_name(
    db: Session,
    *,
    tenant_id: str | UUID | None,
    name: str,
) -> McpServer | None:
    tid = _tenant_uuid(tenant_id, where="get_mcp_server_by_name")
    return db.scalar(
        select(McpServer).where(
            McpServer.tenant_id == tid,
            McpServer.name == name,
        )
    )


def get_mcp_server(
    db: Session,
    *,
    tenant_id: str | UUID | None,
    server_id: UUID | str,
) -> McpServer | None:
    """Load one ``mcp_servers`` row by id, scoped to the tenant."""
    tid = _tenant_uuid(tenant_id, where="get_mcp_server")
    return db.scalar(
        select(McpServer).where(
            McpServer.tenant_id == tid,
            McpServer.id == UUID(str(server_id)),
        )
    )


# ── Tool registry ──


def insert_tool_registry(
    db: Session,
    *,
    tenant_id: str | UUID | None,
    name: str,
    kind: str,
    description: str | None = None,
    mcp_server_id: UUID | None = None,
    config: dict[str, Any] | None = None,
    secret: str | None = None,
    settings: Settings | None = None,
) -> ToolRegistry:
    tid = _tenant_uuid(tenant_id, where="insert_tool_registry")
    secret_encrypted: str | None = None
    if secret:
        secret_encrypted = encrypt_bot_token(secret, settings or Settings())
    row = ToolRegistry(
        tenant_id=tid,
        name=name,
        description=description,
        kind=kind,
        mcp_server_id=mcp_server_id,
        config=config,
        secret_encrypted=secret_encrypted,
    )
    db.add(row)
    db.flush()
    return row


def list_tool_registry(db: Session, *, tenant_id: str | UUID | None) -> list[ToolRegistry]:
    tid = _tenant_uuid(tenant_id, where="list_tool_registry")
    return list(db.scalars(select(ToolRegistry).where(ToolRegistry.tenant_id == tid)).all())


def get_tool_registry(
    db: Session,
    *,
    tenant_id: str | UUID | None,
    name: str,
) -> ToolRegistry | None:
    tid = _tenant_uuid(tenant_id, where="get_tool_registry")
    return db.scalar(
        select(ToolRegistry).where(
            ToolRegistry.tenant_id == tid,
            ToolRegistry.name == name,
        )
    )


def update_tool_registry(
    db: Session,
    *,
    tenant_id: str | UUID | None,
    name: str,
    description: str | None = _UNSET,
    kind: str | None = _UNSET,
    config: dict[str, Any] | None | object = _UNSET,
) -> ToolRegistry | None:
    """Update a tool_registry row by tenant + name. Returns None if not found."""
    row = get_tool_registry(db, tenant_id=tenant_id, name=name)
    if row is None:
        return None
    if description is not _UNSET:
        row.description = description
    if kind is not _UNSET and kind is not None:
        row.kind = kind
    if config is not _UNSET:
        row.config = config
    db.flush()
    return row


def delete_tool_registry(
    db: Session,
    *,
    tenant_id: str | UUID | None,
    name: str,
) -> bool:
    """Delete a tool_registry row by tenant + name. Returns True if deleted."""
    row = get_tool_registry(db, tenant_id=tenant_id, name=name)
    if row is None:
        return False
    db.delete(row)
    db.flush()
    return True


def decrypt_tool_secret(row: ToolRegistry, settings: Settings | None = None) -> Optional[str]:
    if not row.secret_encrypted:
        return None
    return decrypt_bot_token(row.secret_encrypted, settings or Settings())


def update_mcp_server(
    db: Session,
    *,
    tenant_id: str | UUID | None,
    name: str,
    enabled: bool | object = _UNSET,
    connection_config: dict[str, Any] | None | object = _UNSET,
    transport: str | object = _UNSET,
) -> McpServer | None:
    """Update an mcp_servers row by tenant + name. Returns None if not found."""
    row = get_mcp_server_by_name(db, tenant_id=tenant_id, name=name)
    if row is None:
        return None
    if enabled is not _UNSET:
        row.enabled = bool(enabled)
    if connection_config is not _UNSET:
        row.connection_config = connection_config
    if transport is not _UNSET and transport is not None:
        row.transport = str(transport)
    db.flush()
    return row

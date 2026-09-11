"""Tenant MCP server install service — URL + per-tenant service credentials.

Org representatives manage installs via tenant APIs; platform admins use
separate admin routes. Both share this domain-neutral install/verify layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.app.agent.mcp_host import (
    McpCheckResult,
    check_mcp_server,
    extract_http_url,
)
from api.app.db.models import McpServer
from api.app.db.tool_store import (
    decrypt_mcp_server_secret,
    delete_mcp_server,
    get_mcp_server,
    get_mcp_server_by_name,
    insert_mcp_server,
    list_mcp_servers,
    update_mcp_server_by_id,
)
from api.app.settings import Settings

_SERVER_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_HTTP_TRANSPORTS = frozenset({"http", "streamable-http", "streamable_http", "sse"})


class McpInstallError(Exception):
    """Domain error for MCP install/update flows."""

    def __init__(self, message: str, *, code: str = "mcp_install_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class McpServerView:
    id: str
    name: str
    transport: str
    url: str | None
    enabled: bool
    has_service_credential: bool
    has_oauth_credential: bool = False
    created_at: str | None = None
    readiness: dict[str, Any] | None = None


def _normalize_name(name: str) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        raise McpInstallError("name is required", code="invalid_name")
    if not _SERVER_NAME_RE.match(cleaned):
        raise McpInstallError(
            "name must match [A-Za-z0-9_-]+",
            code="invalid_name",
        )
    return cleaned


def _normalize_url(url: str) -> str:
    cleaned = (url or "").strip()
    if not cleaned:
        raise McpInstallError("url is required", code="invalid_url")
    return cleaned


def _normalize_transport(transport: str | None) -> str:
    raw = (transport or "http").strip().lower().replace("_", "-")
    if raw in {"streamable-http", "streamablehttp"}:
        return "http"
    if raw not in _HTTP_TRANSPORTS and raw != "http":
        raise McpInstallError(
            "only remote HTTP MCP URLs are supported for install",
            code="unsupported_transport",
        )
    return "http"


def _connection_config(url: str) -> dict[str, Any]:
    return {"url": url, "auth": "bearer"}


def server_to_view(
    row: McpServer,
    *,
    readiness: McpCheckResult | None = None,
    settings: Settings | None = None,
) -> McpServerView:
    from api.app.mcp_servers.oauth import oauth_connected

    cfg = row.connection_config if isinstance(row.connection_config, dict) else None
    ready_payload: dict[str, Any] | None = None
    if readiness is not None:
        ready_payload = {
            "ready": readiness.ready,
            "endpoint": readiness.endpoint,
            "tool_count": readiness.tool_count,
            "tool_names": list(readiness.tool_names),
            "error": readiness.error,
            "detail": readiness.detail,
        }
    cfg_settings = settings or Settings()
    return McpServerView(
        id=str(row.id),
        name=row.name,
        transport=row.transport,
        url=extract_http_url(cfg),
        enabled=bool(row.enabled),
        has_service_credential=bool(row.secret_encrypted),
        has_oauth_credential=oauth_connected(row, cfg_settings),
        created_at=row.created_at.isoformat() if row.created_at else None,
        readiness=ready_payload,
    )


def verify_remote_mcp(
    *,
    name: str,
    url: str,
    service_token: str | None,
    settings: Settings,
    enabled: bool = True,
) -> McpCheckResult:
    """Industry-standard MCP handshake: initialize + tools/list over HTTP."""
    return check_mcp_server(
        server_name=name,
        transport="http",
        connection_config=_connection_config(url),
        enabled=enabled,
        timeout_seconds=float(settings.mcp_host_check_timeout_seconds),
        service_token=service_token,
    )


def list_tenant_mcp_servers(db: Session, *, tenant_id: str | UUID) -> list[McpServerView]:
    rows = list_mcp_servers(db, tenant_id=tenant_id)
    views = [server_to_view(row) for row in rows]
    views.sort(key=lambda v: v.name.lower())
    return views


def get_tenant_mcp_server(
    db: Session,
    *,
    tenant_id: str | UUID,
    server_id: str | UUID,
) -> McpServerView | None:
    row = get_mcp_server(db, tenant_id=tenant_id, server_id=server_id)
    if row is None:
        return None
    return server_to_view(row)


def install_tenant_mcp_server(
    db: Session,
    *,
    tenant_id: str | UUID,
    name: str,
    url: str,
    service_token: str | None,
    settings: Settings,
    enabled: bool = True,
    verify: bool = True,
) -> McpServerView:
    """Install a remote MCP URL for a tenant; live immediately when enabled."""
    clean_name = _normalize_name(name)
    clean_url = _normalize_url(url)
    transport = _normalize_transport("http")
    if get_mcp_server_by_name(db, tenant_id=tenant_id, name=clean_name) is not None:
        raise McpInstallError(
            f"MCP server {clean_name!r} already exists",
            code="duplicate_name",
        )

    readiness: McpCheckResult | None = None
    if verify:
        readiness = verify_remote_mcp(
            name=clean_name,
            url=clean_url,
            service_token=service_token,
            settings=settings,
            enabled=True,
        )

    try:
        row = insert_mcp_server(
            db,
            tenant_id=tenant_id,
            name=clean_name,
            transport=transport,
            connection_config=_connection_config(clean_url),
            enabled=enabled,
            secret=service_token,
            settings=settings,
        )
    except IntegrityError as exc:
        raise McpInstallError(
            f"MCP server {clean_name!r} already exists",
            code="duplicate_name",
        ) from exc

    db.flush()
    return server_to_view(row, readiness=readiness)


def update_tenant_mcp_server(
    db: Session,
    *,
    tenant_id: str | UUID,
    server_id: str | UUID,
    settings: Settings,
    name: str | None = None,
    url: str | None = None,
    service_token: str | None = None,
    clear_service_token: bool = False,
    enabled: bool | None = None,
    verify: bool = True,
) -> McpServerView:
    row = get_mcp_server(db, tenant_id=tenant_id, server_id=server_id)
    if row is None:
        raise McpInstallError("mcp server not found", code="not_found")

    next_name = _normalize_name(name) if name is not None else row.name
    cfg = row.connection_config if isinstance(row.connection_config, dict) else {}
    next_url = _normalize_url(url) if url is not None else (extract_http_url(cfg) or "")
    if not next_url:
        raise McpInstallError("url is required", code="invalid_url")

    token_for_verify: str | None
    if clear_service_token:
        token_for_verify = None
    elif service_token is not None:
        token_for_verify = service_token
    else:
        from api.app.mcp_servers.oauth import access_token_for_mcp_server

        token_for_verify = access_token_for_mcp_server(
            row,
            settings,
            service_token=decrypt_mcp_server_secret(row, settings),
        )

    readiness: McpCheckResult | None = None
    if verify:
        readiness = verify_remote_mcp(
            name=next_name,
            url=next_url,
            service_token=token_for_verify,
            settings=settings,
            enabled=True,
        )

    kwargs: dict[str, Any] = {
        "name": next_name,
        "transport": "http",
        "connection_config": _connection_config(next_url),
        "enabled": enabled if enabled is not None else row.enabled,
        "settings": settings,
    }
    if clear_service_token:
        kwargs["secret"] = None
    elif service_token is not None:
        kwargs["secret"] = service_token

    updated = update_mcp_server_by_id(
        db,
        tenant_id=tenant_id,
        server_id=server_id,
        **kwargs,
    )
    if updated is None:
        raise McpInstallError("mcp server not found", code="not_found")
    return server_to_view(updated, readiness=readiness)


def delete_tenant_mcp_server(
    db: Session,
    *,
    tenant_id: str | UUID,
    server_id: str | UUID,
) -> bool:
    return delete_mcp_server(db, tenant_id=tenant_id, server_id=server_id)


def set_tenant_mcp_server_enabled(
    db: Session,
    *,
    tenant_id: str | UUID,
    server_id: str | UUID,
    enabled: bool,
) -> McpServerView:
    updated = update_mcp_server_by_id(
        db,
        tenant_id=tenant_id,
        server_id=server_id,
        enabled=enabled,
    )
    if updated is None:
        raise McpInstallError("mcp server not found", code="not_found")
    return server_to_view(updated)


def check_tenant_mcp_server(
    db: Session,
    *,
    tenant_id: str | UUID,
    server_id: str | UUID,
    settings: Settings,
) -> McpServerView:
    from api.app.mcp_servers.oauth import access_token_for_mcp_server

    row = get_mcp_server(db, tenant_id=tenant_id, server_id=server_id)
    if row is None:
        raise McpInstallError("mcp server not found", code="not_found")
    cfg = row.connection_config if isinstance(row.connection_config, dict) else None
    service = decrypt_mcp_server_secret(row, settings)
    token = access_token_for_mcp_server(row, settings, service_token=service)
    db.flush()
    readiness = check_mcp_server(
        server_name=row.name,
        transport=row.transport,
        connection_config=cfg,
        enabled=bool(row.enabled),
        timeout_seconds=float(settings.mcp_host_check_timeout_seconds),
        service_token=token,
    )
    return server_to_view(row, readiness=readiness, settings=settings)

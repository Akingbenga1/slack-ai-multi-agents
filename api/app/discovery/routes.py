"""System-wide tool discovery HTTP routes (not tenant-scoped)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.app.auth.deps import get_current_principal
from api.app.auth.tokens import AuthPrincipal
from api.app.discovery.base import (
    DiscoveredTool,
    DiscoveryNotConfiguredError,
    DiscoveryUpstreamError,
    ToolDiscoveryClient,
    ToolKind,
    kind_configured,
    SUPPORTED_KINDS,
)
from api.app.discovery.deps import get_discovery_client
from api.app.discovery.cli_normalize import normalize_cli_discovered_tool
from api.app.discovery.models import (
    DiscoverySearchBody,
    DiscoverySearchResponse,
    DiscoveryStatusResponse,
    DiscoveredToolResponse,
    KindStatus,
)
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings

logger = get_logger("api.discovery.routes")

router = APIRouter(prefix="/discovery", tags=["discovery"])

_ENV_KEYS: dict[ToolKind, str] = {
    "cli": "DISCOVERY_CLI_DB_PATH",
    "mcp": "DISCOVERY_MCP_SERVICE_URL",
    "http": "DISCOVERY_HTTP_SERVICE_URL",
}


def _to_response(tool: DiscoveredTool) -> DiscoveredToolResponse:
    return DiscoveredToolResponse(
        id=tool.id,
        name=tool.name,
        summary=tool.summary,
        source=tool.source,
        kind=tool.kind,
        config=tool.config,
        metadata=tool.metadata or None,
    )


def _not_configured_http(kind: ToolKind) -> HTTPException:
    env_key = _ENV_KEYS[kind]
    if kind == "cli":
        message = (
            f"{env_key} SQLite DB is missing; run tldr CLI refresh "
            "(Celery worker.refresh_tldr_cli_db or python tldr_search.py --update)"
        )
    else:
        message = (
            f"{env_key} is not set; discovery for kind {kind!r} is unavailable"
        )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "discovery_not_configured",
            "kind": kind,
            "env_key": env_key,
            "message": message,
        },
    )


def _run_search(
    *,
    kind: ToolKind,
    query: str,
    client: ToolDiscoveryClient,
    settings: Settings,
) -> DiscoverySearchResponse:
    q = (query or "").strip()
    if not q:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "discovery_query_required", "message": "query is required"},
        )
    if not kind_configured(settings, kind):
        raise _not_configured_http(kind)
    try:
        tools = client.search(kind, q)
    except DiscoveryNotConfiguredError as exc:
        raise _not_configured_http(exc.kind) from exc
    except DiscoveryUpstreamError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc), "kind": kind},
        ) from exc

    logger.info("discovery_ok kind=%s query_len=%s hits=%s", kind, len(q), len(tools))
    if kind == "cli":
        tools = [normalize_cli_discovered_tool(t) for t in tools]
    return DiscoverySearchResponse(
        kind=kind,
        query=q,
        tools=[_to_response(t) for t in tools],
    )


@router.get("", response_model=DiscoveryStatusResponse)
def discovery_status(
    _: Annotated[AuthPrincipal, Depends(get_current_principal)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DiscoveryStatusResponse:
    """Report which discovery kinds are ready (CLI DB present / MCP URL set)."""
    kinds = {
        kind: KindStatus(
            configured=kind_configured(settings, kind),
            env_key=_ENV_KEYS[kind],
        )
        for kind in SUPPORTED_KINDS
    }
    return DiscoveryStatusResponse(kinds=kinds)


@router.get("/cli-tools", response_model=DiscoverySearchResponse)
def discover_cli_tools_get(
    _: Annotated[AuthPrincipal, Depends(get_current_principal)],
    client: Annotated[ToolDiscoveryClient, Depends(get_discovery_client)],
    settings: Annotated[Settings, Depends(get_settings)],
    query: Annotated[str, Query(min_length=1, max_length=512)],
) -> DiscoverySearchResponse:
    return _run_search(kind="cli", query=query, client=client, settings=settings)


@router.post("/cli-tools", response_model=DiscoverySearchResponse)
def discover_cli_tools_post(
    body: DiscoverySearchBody,
    _: Annotated[AuthPrincipal, Depends(get_current_principal)],
    client: Annotated[ToolDiscoveryClient, Depends(get_discovery_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DiscoverySearchResponse:
    return _run_search(kind="cli", query=body.query, client=client, settings=settings)


@router.get("/mcp-tools", response_model=DiscoverySearchResponse)
def discover_mcp_tools_get(
    _: Annotated[AuthPrincipal, Depends(get_current_principal)],
    client: Annotated[ToolDiscoveryClient, Depends(get_discovery_client)],
    settings: Annotated[Settings, Depends(get_settings)],
    query: Annotated[str, Query(min_length=1, max_length=512)],
) -> DiscoverySearchResponse:
    return _run_search(kind="mcp", query=query, client=client, settings=settings)


@router.post("/mcp-tools", response_model=DiscoverySearchResponse)
def discover_mcp_tools_post(
    body: DiscoverySearchBody,
    _: Annotated[AuthPrincipal, Depends(get_current_principal)],
    client: Annotated[ToolDiscoveryClient, Depends(get_discovery_client)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DiscoverySearchResponse:
    return _run_search(kind="mcp", query=body.query, client=client, settings=settings)

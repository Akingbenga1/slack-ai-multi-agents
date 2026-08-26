"""Official MCP Registry discovery client (system-wide, not tenant-scoped).

Queries ``GET {base}/v0.1/servers?search=…&version=latest`` and normalizes
``server.json`` entries into ``DiscoveredTool`` candidates.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Optional
from urllib.parse import urljoin

import httpx

from api.app.discovery.base import (
    DiscoveredTool,
    DiscoveryNotConfiguredError,
    DiscoveryUpstreamError,
    ToolKind,
)
from api.app.logging_config import get_logger
from api.app.settings import Settings

logger = get_logger("api.discovery.mcp_registry")

_OFFICIAL_META_KEY = "io.modelcontextprotocol.registry/official"


class _TtlCache:
    """Tiny process-local TTL cache for registry search results."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, tuple[float, list[DiscoveredTool]]] = {}

    def get(self, key: str) -> list[DiscoveredTool] | None:
        now = time.monotonic()
        with self._lock:
            row = self._items.get(key)
            if row is None:
                return None
            expires_at, tools = row
            if expires_at <= now:
                self._items.pop(key, None)
                return None
            return list(tools)

    def set(self, key: str, tools: list[DiscoveredTool], *, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            return
        with self._lock:
            self._items[key] = (time.monotonic() + ttl_seconds, list(tools))


_SEARCH_CACHE = _TtlCache()


class OfficialMcpRegistryClient:
    """Concrete MCP discovery via the Official MCP Registry REST API."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        cache: _TtlCache | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._cache = cache if cache is not None else _SEARCH_CACHE

    def search(self, kind: ToolKind, query: str) -> list[DiscoveredTool]:
        if kind != "mcp":
            raise DiscoveryNotConfiguredError(kind)

        q = (query or "").strip()
        if not q:
            return []

        base = mcp_registry_base_url(self._settings)
        if not base:
            raise DiscoveryNotConfiguredError("mcp")

        cache_key = f"{base}|{q.lower()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("mcp_registry_cache_hit query_len=%s hits=%s", len(q), len(cached))
            return cached

        limit = max(1, min(int(self._settings.discovery_mcp_search_limit), 50))
        url = urljoin(base.rstrip("/") + "/", "v0.1/servers")
        params = {"search": q, "limit": str(limit), "version": "latest"}
        timeout = self._settings.discovery_timeout_seconds
        logger.info("mcp_registry_search url=%s query_len=%s limit=%s", url, len(q), limit)

        try:
            with httpx.Client(timeout=timeout, transport=self._transport) as client:
                resp = client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise DiscoveryUpstreamError(
                "MCP registry timed out",
                code="discovery_upstream_timeout",
                status_code=504,
            ) from exc
        except httpx.HTTPError as exc:
            raise DiscoveryUpstreamError(
                "MCP registry request failed",
                code="discovery_upstream_error",
                status_code=502,
            ) from exc

        if resp.status_code >= 400:
            raise DiscoveryUpstreamError(
                f"MCP registry returned {resp.status_code}",
                code="discovery_upstream_error",
                status_code=502,
            )

        try:
            payload = resp.json()
        except ValueError as exc:
            raise DiscoveryUpstreamError(
                "MCP registry returned non-JSON body",
            ) from exc

        tools = _normalize_registry_payload(payload, default_source=base)
        self._cache.set(
            cache_key,
            tools,
            ttl_seconds=float(self._settings.discovery_mcp_cache_ttl_seconds),
        )
        return tools


def mcp_registry_base_url(settings: Settings) -> str:
    """Resolve MCP registry base URL; empty disables MCP discovery."""
    return (settings.discovery_mcp_service_url or "").strip()


def _normalize_registry_payload(
    payload: Any,
    *,
    default_source: str,
) -> list[DiscoveredTool]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("servers")
    if not isinstance(rows, list):
        return []

    out: list[DiscoveredTool] = []
    for row in rows:
        tool = _server_row_to_tool(row, default_source=default_source)
        if tool is not None:
            out.append(tool)
    return out


def _server_row_to_tool(row: Any, *, default_source: str) -> Optional[DiscoveredTool]:
    if not isinstance(row, dict):
        return None

    server = row.get("server")
    if not isinstance(server, dict):
        # Tolerate a bare server.json object
        server = row if "name" in row else None
    if not isinstance(server, dict):
        return None

    server_name = str(server.get("name") or "").strip()
    if not server_name:
        return None

    summary = str(server.get("description") or "").strip()
    version = str(server.get("version") or "").strip()
    repo = server.get("repository")
    repo_url = ""
    if isinstance(repo, dict):
        repo_url = str(repo.get("url") or "").strip()

    packages = server.get("packages") if isinstance(server.get("packages"), list) else []
    remotes = server.get("remotes") if isinstance(server.get("remotes"), list) else []
    transport = _primary_transport(packages=packages, remotes=remotes)

    meta_block = row.get("_meta") if isinstance(row.get("_meta"), dict) else {}
    official = meta_block.get(_OFFICIAL_META_KEY) if isinstance(meta_block, dict) else None
    published_at = ""
    is_latest = None
    status = ""
    if isinstance(official, dict):
        published_at = str(official.get("publishedAt") or "").strip()
        is_latest = official.get("isLatest")
        status = str(official.get("status") or "").strip()

    website = str(server.get("websiteUrl") or "").strip()
    source = repo_url or website or default_source

    metadata: dict[str, Any] = {
        "version": version or None,
        "repository": repo_url or None,
        "websiteUrl": website or None,
        "transport": transport,
        "packages": packages,
        "remotes": remotes,
        "publishedAt": published_at or None,
        "status": status or None,
        "isLatest": is_latest,
        "official": bool(official),
    }
    # Drop nullish cosmetic keys for cleaner JSON
    metadata = {k: v for k, v in metadata.items() if v is not None and v != []}

    display = server_name.split("/")[-1] if "/" in server_name else server_name

    return DiscoveredTool(
        id=server_name,
        name=display,
        summary=summary,
        source=source,
        kind="mcp",
        metadata=metadata,
    )


def _primary_transport(*, packages: list[Any], remotes: list[Any]) -> str | None:
    for pkg in packages:
        if not isinstance(pkg, dict):
            continue
        transport = pkg.get("transport")
        if isinstance(transport, dict):
            t = str(transport.get("type") or "").strip()
            if t:
                return t
        t = str(pkg.get("transport") or "").strip()
        if t and t != "{}":
            return t
    for remote in remotes:
        if not isinstance(remote, dict):
            continue
        t = str(remote.get("type") or "").strip()
        if t:
            return t
    return None

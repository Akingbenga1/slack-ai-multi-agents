"""Abstract tool discovery — callers depend on this, not on HTTP details."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from api.app.settings import Settings

ToolKind = Literal["cli", "mcp", "http"]

SUPPORTED_KINDS: tuple[ToolKind, ...] = ("cli", "mcp", "http")


@dataclass(frozen=True)
class DiscoveredTool:
    """Normalized candidate from an upstream discovery service."""

    id: str
    name: str
    summary: str
    source: str
    kind: ToolKind
    metadata: dict[str, Any] = field(default_factory=dict)
    # CLI tools: tool_registry-aligned config (command / args / subcommands).
    config: dict[str, Any] | None = None


class DiscoveryNotConfiguredError(Exception):
    """No upstream URL configured for the requested kind."""

    _ENV_KEYS: dict[ToolKind, str] = {
        "cli": "DISCOVERY_CLI_DB_PATH",
        "mcp": "DISCOVERY_MCP_SERVICE_URL",
        "http": "DISCOVERY_HTTP_SERVICE_URL",
    }

    def __init__(self, kind: ToolKind) -> None:
        self.kind = kind
        self.code = "discovery_not_configured"
        self.env_key = self._ENV_KEYS[kind]
        super().__init__(
            f"{self.env_key} is not set; discovery for kind {kind!r} is unavailable"
        )


class DiscoveryUpstreamError(Exception):
    """Upstream discovery service failed or returned unusable data."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "discovery_upstream_error",
        status_code: int = 502,
    ) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class ToolDiscoveryClient(Protocol):
    """Single search entry — kind is a parameter, not separate methods."""

    def search(self, kind: ToolKind, query: str) -> list[DiscoveredTool]:
        ...


def service_url_for_kind(settings: Settings, kind: ToolKind) -> str:
    """Resolve the env-configured upstream URL for HTTP-backed discovery kinds."""
    mapping: dict[ToolKind, str] = {
        "mcp": settings.discovery_mcp_service_url,
        "http": settings.discovery_http_service_url,
    }
    return (mapping.get(kind) or "").strip()


def kind_configured(settings: Settings, kind: ToolKind) -> bool:
    """CLI uses the local tldr SQLite DB; MCP/HTTP use upstream service URLs."""
    if kind == "cli":
        from api.app.discovery.cli_client import cli_db_configured

        return cli_db_configured(settings)
    return bool(service_url_for_kind(settings, kind))

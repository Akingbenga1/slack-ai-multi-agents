"""FastAPI dependency for the tool discovery client."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from api.app.discovery.base import ToolDiscoveryClient, ToolKind
from api.app.discovery.composite import CompositeDiscoveryClient
from api.app.discovery.http_client import HttpToolDiscoveryClient
from api.app.discovery.mcp_registry import OfficialMcpRegistryClient
from api.app.discovery.cli_client import CliDiscoveryClient
from api.app.settings import Settings, get_settings


def get_discovery_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ToolDiscoveryClient:
    """Build a composite client: CLI via local SQLite, MCP via Official Registry."""
    cli = CliDiscoveryClient(settings)
    http = HttpToolDiscoveryClient(settings)
    mcp = OfficialMcpRegistryClient(settings)
    clients: dict[ToolKind, ToolDiscoveryClient] = {
        "cli": cli,
        "mcp": mcp,
        "http": http,
    }
    return CompositeDiscoveryClient(clients)

"""Route discovery kinds to concrete clients (tldr CLI DB vs Official MCP Registry)."""

from __future__ import annotations

from api.app.discovery.base import (
    DiscoveredTool,
    DiscoveryNotConfiguredError,
    ToolDiscoveryClient,
    ToolKind,
)


class CompositeDiscoveryClient:
    """Delegates ``search(kind, query)`` to a per-kind concrete client."""

    def __init__(self, clients: dict[ToolKind, ToolDiscoveryClient]) -> None:
        self._clients = dict(clients)

    def search(self, kind: ToolKind, query: str) -> list[DiscoveredTool]:
        client = self._clients.get(kind)
        if client is None:
            raise DiscoveryNotConfiguredError(kind)
        return client.search(kind, query)

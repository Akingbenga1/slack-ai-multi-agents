"""MCP tool: ``search_knowledge`` — wraps API retrieval with required tenant."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from api.app.qdrant.tenant import TenantFilterRequired
from api.app.retrieval import KnowledgeSearchFilters, search_knowledge
from api.app.retrieval.types import KnowledgeSearchResult
from mcp_server.serialize import search_result_to_dict
from mcp_server.tenant_bind import require_tool_client_id

SearchFn = Callable[..., KnowledgeSearchResult]


def search_knowledge_tool(
    *,
    client_id: str | None,
    query: str,
    limit: int = 8,
    kind: str | None = None,
    channel: str | None = None,
    filename: str | None = None,
    search_fn: SearchFn | None = None,
    **search_kwargs: Any,
) -> dict[str, Any]:
    """
    Run tenant-scoped ``search_knowledge`` and return a JSON-friendly dict.

    Raises ``TenantFilterRequired`` / ``ValueError`` on bad input (surfaced
    by FastMCP as tool errors).
    """
    cid = require_tool_client_id(client_id)
    text = (query or "").strip()
    if not text:
        raise ValueError("query must be non-empty")

    filters = KnowledgeSearchFilters.from_mapping(
        {"kind": kind, "channel": channel, "filename": filename}
    )
    fn = search_fn or search_knowledge
    from api.app.settings import get_settings

    max_k = int(getattr(get_settings(), "agent_retrieve_max_top_k", 32) or 32)
    max_k = max(1, max_k)
    capped = min(max(1, int(limit)), max_k)
    result = fn(
        client_id=cid,
        query=text,
        limit=capped,
        filters=filters,
        **search_kwargs,
    )
    return search_result_to_dict(result)


__all__ = ["TenantFilterRequired", "search_knowledge_tool"]

"""Retrieve helpers — quarantined DirectRetrieveStrategy (tests / direct backend).

Production agent path uses ``nodes.tools`` → ToolStrategy → MCP (Sprint 15.4+ / 25.4).
``make_retrieve_node`` remains for debug graphs and unit tests that want a
standalone retrieve step without the full tools Strategy map.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from api.app.agent.state import AgentState
from api.app.retrieval import search_knowledge
from api.app.retrieval.types import KnowledgeSearchResult
from api.app.settings import Settings, get_settings

SearchFn = Callable[..., KnowledgeSearchResult]


def make_retrieve_node(
    *,
    settings: Settings | None = None,
    search_fn: Optional[SearchFn] = None,
    top_k: int | None = None,
) -> Callable[[AgentState], dict[str, Any]]:
    """Build a retrieve node backed by ``DirectRetrieveStrategy`` (debug/tests)."""

    # Lazy import: tool_strategies imports SearchFn from this module.
    from api.app.agent.workflows.tool_strategies import DIRECT_RETRIEVE

    settings = settings or get_settings()
    search = search_fn or search_knowledge
    limit = top_k if top_k is not None else settings.agent_retrieve_top_k

    def retrieve_node(state: AgentState) -> dict[str, Any]:
        return DIRECT_RETRIEVE.run(
            state,
            settings=settings,
            search=search,
            limit=limit,
        )

    return retrieve_node

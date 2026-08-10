"""Retrieve helpers — in-process RAG (tests / AGENT_RETRIEVE_BACKEND=direct).

Production agent path uses ``nodes.tools`` → MCP client (Sprint 15.4).
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from api.app.agent.chunks import citation_to_chunk
from api.app.agent.guardrails import (
    filter_chunks_for_tenant,
    require_tenant_client_id,
    should_hedge,
)
from api.app.agent.state import AgentState
from api.app.logging_config import get_logger
from api.app.retrieval import search_knowledge
from api.app.retrieval.types import KnowledgeSearchResult
from api.app.settings import Settings, get_settings

logger = get_logger("api.agent.nodes.retrieve")

SearchFn = Callable[..., KnowledgeSearchResult]


def make_retrieve_node(
    *,
    settings: Settings | None = None,
    search_fn: Optional[SearchFn] = None,
    top_k: int | None = None,
) -> Callable[[AgentState], dict[str, Any]]:
    """Build a retrieve node; inject `search_fn` in tests."""

    settings = settings or get_settings()
    search = search_fn or search_knowledge
    limit = top_k if top_k is not None else settings.agent_retrieve_top_k

    def retrieve_node(state: AgentState) -> dict[str, Any]:
        client_id = require_tenant_client_id(
            state.get("client_id"),
            where="retrieve",
        )

        question = (state.get("question") or "").strip()
        if not question:
            logger.info("agent_retrieve skip empty question client_id=%s", client_id)
            return {
                "client_id": client_id,
                "retrieved_chunks": [],
                "hedge": True,
            }

        min_score = float(settings.agent_min_score)
        result = search(
            client_id=client_id,
            query=question,
            limit=limit,
            score_threshold=min_score,
            settings=settings,
        )
        # Defense in depth: drop foreign tenants + weak scores
        raw = [citation_to_chunk(h) for h in result.hits]
        chunks = filter_chunks_for_tenant(raw, client_id, min_score=min_score)
        hedge = should_hedge(chunks)
        logger.info(
            "agent_retrieve client_id=%s hits=%s hedge=%s",
            client_id,
            len(chunks),
            hedge,
        )
        return {
            "client_id": client_id,
            "retrieved_chunks": chunks,
            "hedge": hedge,
        }

    return retrieve_node

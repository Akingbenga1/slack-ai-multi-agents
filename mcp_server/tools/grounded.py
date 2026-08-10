"""Template Method for grounded MCP draft tools (Sprint 27.1).

Skeleton: search → citations → hedge → payload.
Strategy: ``outline_fn(citations)`` supplies title / markdown / sections|items.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from api.app.qdrant.tenant import require_client_id
from api.app.retrieval.types import KnowledgeCitation, KnowledgeSearchResult
from mcp_server.serialize import citation_to_dict, search_result_to_dict
from mcp_server.tools.search import search_knowledge_tool

SearchToolFn = Callable[..., dict[str, Any]]
OutlineFn = Callable[[list[KnowledgeCitation]], Mapping[str, Any]]


def hit_as_citation(h: Mapping[str, Any]) -> KnowledgeCitation:
    """Normalize one retrieval hit dict into a ``KnowledgeCitation``."""
    return KnowledgeCitation(
        point_id=str(h.get("point_id") or ""),
        score=float(h.get("score") or 0.0),
        text=str(h.get("text") or ""),
        kind=str(h.get("kind") or "unknown"),
        client_id=str(h.get("client_id") or ""),
        channel=h.get("channel"),
        ts=h.get("ts"),
        user=h.get("user"),
        thread_ts=h.get("thread_ts"),
        filename=h.get("filename"),
        locator=h.get("locator"),
        title=h.get("title"),
        source_format=h.get("source_format"),
        chunk_index=h.get("chunk_index"),
    )


def excerpt(text: str, max_len: int = 160) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def run_grounded_draft(
    *,
    client_id: str | None,
    query: str,
    outline_fn: OutlineFn,
    limit: int = 8,
    kind: str | None = None,
    channel: str | None = None,
    filename: str | None = None,
    search_tool_fn: SearchToolFn | None = None,
    prefer_kind: str | None = None,
    empty_note: str,
    evidence_note: str,
) -> dict[str, Any]:
    """
    Shared grounded-draft pipeline.

    1. Require tenant ``client_id`` and run knowledge search.
    2. Map hits → citations (optionally widen when ``prefer_kind`` yields nothing).
    3. Call ``outline_fn(citations)`` for tool-specific body fields.
    4. Attach citations / retrieval / hedge note.
    """
    cid = require_client_id(client_id)
    q = (query or "").strip()
    if not q:
        raise ValueError("query must be non-empty")

    search = search_tool_fn or search_knowledge_tool
    search_kind = kind if kind is not None else prefer_kind
    raw = search(
        client_id=cid,
        query=q,
        limit=limit,
        kind=search_kind,
        channel=channel,
        filename=filename,
    )
    hits = raw.get("hits") or []
    citations = [hit_as_citation(h) for h in hits if isinstance(h, Mapping)]

    if not citations and prefer_kind is not None and kind is None:
        raw = search(
            client_id=cid,
            query=q,
            limit=limit,
            kind=None,
            channel=channel,
            filename=filename,
        )
        hits = raw.get("hits") or []
        citations = [hit_as_citation(h) for h in hits if isinstance(h, Mapping)]

    outline = dict(outline_fn(citations))
    hedged = len(citations) == 0
    retrieval = (
        raw
        if "query" in raw
        else search_result_to_dict(
            KnowledgeSearchResult(
                client_id=cid, query=q, hits=citations, limit=limit
            )
        )
    )
    return {
        "client_id": cid,
        **outline,
        "citations": [citation_to_dict(c) for c in citations],
        "retrieval": retrieval,
        "hedged": hedged,
        "note": empty_note if hedged else evidence_note,
    }


__all__ = [
    "OutlineFn",
    "SearchToolFn",
    "excerpt",
    "hit_as_citation",
    "run_grounded_draft",
]

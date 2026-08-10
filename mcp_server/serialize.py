"""Serialize retrieval results for MCP tool responses."""

from __future__ import annotations

from typing import Any

from api.app.retrieval.types import KnowledgeCitation, KnowledgeSearchResult


def citation_to_dict(c: KnowledgeCitation) -> dict[str, Any]:
    return {
        "point_id": c.point_id,
        "score": c.score,
        "text": c.text,
        "kind": c.kind,
        "client_id": c.client_id,
        "label": c.short_label(),
        "channel": c.channel,
        "ts": c.ts,
        "user": c.user,
        "thread_ts": c.thread_ts,
        "filename": c.filename,
        "locator": c.locator,
        "title": c.title,
        "source_format": c.source_format,
        "chunk_index": c.chunk_index,
    }


def search_result_to_dict(result: KnowledgeSearchResult) -> dict[str, Any]:
    return {
        "client_id": result.client_id,
        "query": result.query,
        "limit": result.limit,
        "hit_count": len(result.hits),
        "hits": [citation_to_dict(h) for h in result.hits],
    }

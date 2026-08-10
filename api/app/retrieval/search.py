"""`search_knowledge` — TEI query embed + tenant-scoped Qdrant top-k."""

from __future__ import annotations

from typing import Mapping, Sequence

from qdrant_client import QdrantClient
from qdrant_client.http import models

from api.app.qdrant.vectors import search_vectors
from api.app.retrieval.citations import citation_from_point
from api.app.retrieval.types import (
    KnowledgeCitation,
    KnowledgeSearchFilters,
    KnowledgeSearchResult,
)
from api.app.settings import Settings, get_settings
from api.app.tei.client import TeiClient

DEFAULT_TOP_K = 8

# Re-export types for `from api.app.retrieval.search import …`
__all__ = [
    "DEFAULT_TOP_K",
    "KnowledgeCitation",
    "KnowledgeSearchFilters",
    "KnowledgeSearchResult",
    "search_knowledge",
]


def search_knowledge(
    *,
    client_id: str | None,
    query: str,
    filters: KnowledgeSearchFilters | Mapping[str, object] | None = None,
    limit: int = DEFAULT_TOP_K,
    score_threshold: float | None = None,
    settings: Settings | None = None,
    tei: TeiClient | None = None,
    client: QdrantClient | None = None,
    ensure_collection: bool = True,
) -> KnowledgeSearchResult:
    """
    Embed ``query`` via TEI and retrieve top-k knowledge chunks for one tenant.

    Always applies a fail-closed ``client_id`` Qdrant filter. Optional filters
    (``kind``, ``channel``, ``filename``) are AND'd with that tenant filter.
    """
    settings = settings or get_settings()
    text = (query or "").strip()
    if not text:
        raise ValueError("query must be non-empty")

    top_k = max(1, int(limit))
    resolved = _resolve_filters(filters)
    tei = tei or TeiClient(settings)
    query_vector = tei.embed(text)[0]

    hits_raw = search_vectors(
        client_id=client_id,
        query_vector=query_vector,
        limit=top_k,
        score_threshold=score_threshold,
        extra_conditions=_filter_conditions(resolved),
        client=client,
        settings=settings,
        ensure_collection=ensure_collection,
    )
    citations = [citation_from_point(p) for p in hits_raw]
    # Defense in depth: drop any hit that somehow lacks matching client_id
    cid = str(client_id).strip() if client_id is not None else ""
    safe = [c for c in citations if c.client_id == cid]

    return KnowledgeSearchResult(
        client_id=cid,
        query=text,
        hits=safe,
        limit=top_k,
    )


def _resolve_filters(
    filters: KnowledgeSearchFilters | Mapping[str, object] | None,
) -> KnowledgeSearchFilters | None:
    if filters is None:
        return None
    if isinstance(filters, KnowledgeSearchFilters):
        return filters
    return KnowledgeSearchFilters.from_mapping(filters)


def _filter_conditions(
    filters: KnowledgeSearchFilters | None,
) -> Sequence[models.Condition] | None:
    if filters is None:
        return None
    conditions: list[models.Condition] = []
    for key, value in (
        ("kind", filters.kind),
        ("channel", filters.channel),
        ("filename", filters.filename),
    ):
        if value is None:
            continue
        conditions.append(
            models.FieldCondition(
                key=key,
                match=models.MatchValue(value=value),
            )
        )
    return conditions or None

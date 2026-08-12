"""`search_knowledge` — query embed + tenant-scoped vector top-k."""

from __future__ import annotations

from typing import Mapping

from api.app.embedding import EmbeddingProvider, get_embedding_provider
from api.app.retrieval.citations import citation_from_hit
from api.app.retrieval.types import (
    KnowledgeCitation,
    KnowledgeSearchFilters,
    KnowledgeSearchResult,
)
from api.app.settings import Settings, get_settings
from api.app.vector_store import VectorStore, get_vector_store

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
    embeddings: EmbeddingProvider | None = None,
    store: VectorStore | None = None,
    ensure_collection: bool = True,
) -> KnowledgeSearchResult:
    """
    Embed ``query`` and retrieve top-k knowledge chunks for one tenant.

    Always applies a fail-closed ``client_id`` store filter. Optional filters
    (``kind``, ``channel``, ``filename``) are AND'd with that tenant filter.
    """
    settings = settings or get_settings()
    text = (query or "").strip()
    if not text:
        raise ValueError("query must be non-empty")

    top_k = max(1, int(limit))
    resolved = _resolve_filters(filters)
    embeddings = embeddings or get_embedding_provider(settings)
    store = store or get_vector_store(settings)
    query_vector = embeddings.embed(text)[0]

    hits_raw = store.search(
        client_id=client_id,
        query_vector=query_vector,
        limit=top_k,
        score_threshold=score_threshold,
        filters=_filter_mapping(resolved),
        ensure_collection=ensure_collection,
    )
    citations = [citation_from_hit(h) for h in hits_raw]
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


def _filter_mapping(
    filters: KnowledgeSearchFilters | None,
) -> dict[str, str] | None:
    if filters is None:
        return None
    out: dict[str, str] = {}
    for key, value in (
        ("kind", filters.kind),
        ("channel", filters.channel),
        ("filename", filters.filename),
    ):
        if value is None:
            continue
        text = str(value).strip()
        if text:
            out[key] = text
    return out or None

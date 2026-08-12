"""Shared embed + upsert core (Sprint 29.1 / 35.3).

Template Method skeleton: embed batches → upsert.
Strategy hooks: ``point_id_fn`` / ``payload_fn`` (Slack message vs document).
Calls ``EmbeddingProvider`` + ``VectorStore`` only (vendor adapters via factory).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Protocol, TypeVar

from api.app.embedding import EmbeddingProvider, get_embedding_provider
from api.app.settings import Settings, get_settings
from api.app.vector_store import VectorStore, get_vector_store

DEFAULT_EMBED_BATCH = 32

TChunk = TypeVar("TChunk")


class _HasText(Protocol):
    text: str


PointIdFn = Callable[[str, TChunk], str]
PayloadFn = Callable[[TChunk], dict[str, Any]]


def ingest_chunks(
    *,
    client_id: str,
    chunks: Sequence[_HasText],
    point_id_fn: Callable[[str, Any], str],
    payload_fn: Callable[[Any], dict[str, Any]],
    settings: Settings | None = None,
    embeddings: EmbeddingProvider | None = None,
    store: VectorStore | None = None,
    embed_batch_size: int = DEFAULT_EMBED_BATCH,
) -> list[str]:
    """
    Embed chunks and upsert into the tenant knowledge collection.

    Returns deterministic point ids (order matches ``chunks``).
    Empty ``chunks`` → empty list (no embed / store calls).
    """
    if not chunks:
        return []

    settings = settings or get_settings()
    embeddings = embeddings or get_embedding_provider(settings)
    store = store or get_vector_store(settings)
    point_ids: list[str] = []
    batch_size = max(1, embed_batch_size)

    for start in range(0, len(chunks), batch_size):
        batch = list(chunks[start : start + batch_size])
        vectors = embeddings.embed([c.text for c in batch])
        ids = [point_id_fn(client_id, c) for c in batch]
        payloads = [payload_fn(c) for c in batch]
        store.upsert(
            client_id=client_id,
            vectors=vectors,
            payloads=payloads,
            ids=ids,
        )
        point_ids.extend(ids)

    return point_ids

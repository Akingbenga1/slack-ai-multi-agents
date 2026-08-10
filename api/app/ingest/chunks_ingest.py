"""Shared TEI batch + Qdrant upsert core (Sprint 29.1).

Template Method skeleton: embed batches → upsert.
Strategy hooks: ``point_id_fn`` / ``payload_fn`` (Slack message vs document).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Protocol, TypeVar

from api.app.qdrant.vectors import upsert_vectors
from api.app.settings import Settings, get_settings
from api.app.tei.client import TeiClient

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
    tei: TeiClient | None = None,
    embed_batch_size: int = DEFAULT_EMBED_BATCH,
) -> list[str]:
    """
    Embed chunks via TEI and upsert into the tenant knowledge collection.

    Returns deterministic Qdrant point ids (order matches ``chunks``).
    Empty ``chunks`` → empty list (no TEI / Qdrant calls).
    """
    if not chunks:
        return []

    settings = settings or get_settings()
    tei = tei or TeiClient(settings)
    point_ids: list[str] = []
    batch_size = max(1, embed_batch_size)

    for start in range(0, len(chunks), batch_size):
        batch = list(chunks[start : start + batch_size])
        vectors = tei.embed([c.text for c in batch])
        ids = [point_id_fn(client_id, c) for c in batch]
        payloads = [payload_fn(c) for c in batch]
        upsert_vectors(
            client_id=client_id,
            vectors=vectors,
            payloads=payloads,
            ids=ids,
            settings=settings,
        )
        point_ids.extend(ids)

    return point_ids

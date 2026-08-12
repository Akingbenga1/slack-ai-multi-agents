"""Qdrant Adapter for ``VectorStore`` (Sprint 35).

Owns ``qdrant_client`` usage via existing ``api.app.qdrant`` helpers.
Tenant ``client_id`` filter stays fail-closed on every call.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from qdrant_client import QdrantClient
from qdrant_client.http import models

from api.app.qdrant.collection import ensure_knowledge_collection
from api.app.qdrant.vectors import search_vectors, upsert_vectors
from api.app.settings import Settings, get_settings
from api.app.vector_store.types import VectorFilters, VectorHit


class QdrantVectorStore:
    """Qdrant upsert / search / ensure-collection adapter."""

    name = "qdrant"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: QdrantClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client

    def ensure_collection(self) -> str:
        return ensure_knowledge_collection(client=self._client, settings=self.settings)

    def upsert(
        self,
        *,
        client_id: str | None,
        vectors: Sequence[Sequence[float]],
        payloads: Sequence[Mapping[str, Any]] | None = None,
        ids: Sequence[str | int] | None = None,
        ensure_collection: bool = True,
    ) -> list[str | int]:
        return upsert_vectors(
            client_id=client_id,
            vectors=vectors,
            payloads=payloads,
            ids=ids,
            client=self._client,
            settings=self.settings,
            ensure_collection=ensure_collection,
        )

    def search(
        self,
        *,
        client_id: str | None,
        query_vector: Sequence[float],
        limit: int = 10,
        score_threshold: float | None = None,
        filters: VectorFilters | None = None,
        ensure_collection: bool = True,
    ) -> list[VectorHit]:
        points = search_vectors(
            client_id=client_id,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            extra_conditions=_filter_conditions(filters),
            client=self._client,
            settings=self.settings,
            ensure_collection=ensure_collection,
        )
        return [_hit_from_point(p) for p in points]


def _filter_conditions(
    filters: VectorFilters | None,
) -> Sequence[models.Condition] | None:
    if not filters:
        return None
    conditions: list[models.Condition] = []
    for key, value in filters.items():
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        conditions.append(
            models.FieldCondition(
                key=key,
                match=models.MatchValue(value=text),
            )
        )
    return conditions or None


def _hit_from_point(point: models.ScoredPoint) -> VectorHit:
    return VectorHit(
        id=str(point.id),
        score=float(point.score) if point.score is not None else 0.0,
        payload=dict(point.payload or {}),
    )

"""Upsert / search helpers that always scope by tenant `client_id`."""

from __future__ import annotations

from typing import Any, Mapping, Sequence
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models

from api.app.http_retry import call_with_retries
from api.app.qdrant.client import get_qdrant_client
from api.app.qdrant.collection import CLIENT_ID_PAYLOAD_KEY, ensure_knowledge_collection
from api.app.qdrant.tenant import TenantFilterRequired, require_client_id, tenant_filter
from api.app.settings import Settings, get_settings


def _qdrant_should_retry(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in {
        "ResponseHandlingException",
        "UnexpectedResponse",
        "ConnectError",
        "ConnectTimeout",
        "ReadTimeout",
        "TimeoutError",
        "ConnectionError",
    }:
        return True
    msg = str(exc).lower()
    return any(
        token in msg
        for token in ("timeout", "temporarily", "unavailable", "connection", "503", "502", "429")
    )


def upsert_vectors(
    *,
    client_id: str | None,
    vectors: Sequence[Sequence[float]],
    payloads: Sequence[Mapping[str, Any]] | None = None,
    ids: Sequence[str | int] | None = None,
    client: QdrantClient | None = None,
    settings: Settings | None = None,
    ensure_collection: bool = True,
) -> list[str | int]:
    """Upsert points for one tenant. Always writes `client_id` into payload."""
    cid = require_client_id(client_id)
    if not vectors:
        raise ValueError("vectors must be non-empty")

    settings = settings or get_settings()
    client = client or get_qdrant_client(settings)
    collection = (
        ensure_knowledge_collection(client=client, settings=settings)
        if ensure_collection
        else settings.qdrant_collection
    )

    n = len(vectors)
    if payloads is not None and len(payloads) != n:
        raise ValueError("payloads length must match vectors")
    if ids is not None and len(ids) != n:
        raise ValueError("ids length must match vectors")

    point_ids: list[str | int] = list(ids) if ids is not None else [str(uuid4()) for _ in range(n)]
    points: list[models.PointStruct] = []
    for i, vector in enumerate(vectors):
        if len(vector) != settings.embedding_dim:
            raise ValueError(
                f"vector dim {len(vector)} != configured embedding_dim {settings.embedding_dim}"
            )
        payload: dict[str, Any] = dict(payloads[i]) if payloads else {}
        existing = payload.get(CLIENT_ID_PAYLOAD_KEY)
        if existing is not None and str(existing).strip() != cid:
            raise TenantFilterRequired(
                f"payload client_id {existing!r} does not match required {cid!r}"
            )
        payload[CLIENT_ID_PAYLOAD_KEY] = cid
        points.append(
            models.PointStruct(
                id=point_ids[i],
                vector=list(vector),
                payload=payload,
            )
        )

    call_with_retries(
        lambda: client.upsert(collection_name=collection, points=points, wait=True),
        max_retries=3,
        should_retry=_qdrant_should_retry,
        label="qdrant.upsert",
    )
    return point_ids


def search_vectors(
    *,
    client_id: str | None,
    query_vector: Sequence[float],
    limit: int = 10,
    score_threshold: float | None = None,
    extra_conditions: Sequence[models.Condition] | None = None,
    client: QdrantClient | None = None,
    settings: Settings | None = None,
    ensure_collection: bool = True,
) -> list[models.ScoredPoint]:
    """Nearest-neighbor search with mandatory tenant filter (fail-closed).

    Optional ``extra_conditions`` are AND'd with the tenant ``client_id`` filter.
    """
    require_client_id(client_id)
    settings = settings or get_settings()
    client = client or get_qdrant_client(settings)
    collection = (
        ensure_knowledge_collection(client=client, settings=settings)
        if ensure_collection
        else settings.qdrant_collection
    )

    if len(query_vector) != settings.embedding_dim:
        raise ValueError(
            f"query vector dim {len(query_vector)} != configured embedding_dim {settings.embedding_dim}"
        )

    must = list(tenant_filter(client_id).must or [])
    if extra_conditions:
        must.extend(extra_conditions)
    query_filter = models.Filter(must=must)

    def _query() -> list[models.ScoredPoint]:
        response = client.query_points(
            collection_name=collection,
            query=list(query_vector),
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
            with_vectors=False,
        )
        return list(response.points)

    return call_with_retries(
        _query,
        max_retries=3,
        should_retry=_qdrant_should_retry,
        label="qdrant.search",
    )

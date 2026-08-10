"""Second-org / multi-tenant knowledge isolation helpers (Sprint 22.4)."""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import QdrantClient

from api.app.qdrant import search_vectors, upsert_vectors
from api.app.retrieval import search_knowledge
from api.app.settings import Settings, get_settings


def _unit_vector(dim: int, hot_index: int) -> list[float]:
    v = [0.0] * dim
    v[hot_index % dim] = 1.0
    return v


def prove_no_knowledge_leak(
    *,
    tenant_a: str,
    tenant_b: str,
    settings: Settings | None = None,
    client: QdrantClient | None = None,
) -> dict[str, Any]:
    """
    Upsert distinct secrets per tenant; search must stay fail-closed on client_id.

    When ``client`` is omitted, tries live Qdrant briefly, else uses in-memory.
    """
    settings = settings or get_settings()
    qclient = client
    if qclient is None:
        try:
            live = QdrantClient(url=settings.qdrant_url, timeout=2.0)
            live.get_collections()
            qclient = live
            mode = "live"
        except Exception:
            qclient = QdrantClient(":memory:")
            mode = "memory"
    else:
        mode = "injected"

    dim = settings.embedding_dim
    vec_a = _unit_vector(dim, 0)
    vec_b = _unit_vector(dim, 1)
    id_a = str(uuid.uuid4())
    id_b = str(uuid.uuid4())
    secret_a = f"alpha-secret-{id_a[:8]}"
    secret_b = f"bravo-secret-{id_b[:8]}"

    upsert_vectors(
        client_id=tenant_a,
        vectors=[vec_a],
        payloads=[
            {
                "kind": "slack_message",
                "channel": "C_A",
                "ts": "1.0",
                "text": secret_a,
                "smoke": "22.4",
            }
        ],
        ids=[id_a],
        client=qclient,
        settings=settings,
    )
    upsert_vectors(
        client_id=tenant_b,
        vectors=[vec_b],
        payloads=[
            {
                "kind": "slack_message",
                "channel": "C_B",
                "ts": "2.0",
                "text": secret_b,
                "smoke": "22.4",
            }
        ],
        ids=[id_b],
        client=qclient,
        settings=settings,
    )

    class _StubTei:
        def embed(self, texts, *, truncate: bool = True):  # noqa: ARG002
            if isinstance(texts, str):
                texts = [texts]
            out = []
            for t in texts:
                lowered = t.lower()
                if "bravo" in lowered or secret_b.lower() in lowered:
                    out.append(list(vec_b))
                else:
                    out.append(list(vec_a))
            return out

    result_a = search_knowledge(
        client_id=tenant_a,
        query=secret_b,
        limit=10,
        settings=settings,
        tei=_StubTei(),  # type: ignore[arg-type]
        client=qclient,
    )
    ids_a = {h.point_id for h in result_a.hits}
    if id_b in ids_a:
        raise AssertionError("tenant A must not retrieve tenant B knowledge")
    if not all(h.client_id == tenant_a for h in result_a.hits):
        raise AssertionError("hit client_id filter failed for tenant A")

    hits_raw_a = search_vectors(
        client_id=tenant_a,
        query_vector=vec_b,
        limit=10,
        client=qclient,
        settings=settings,
    )
    if id_b in {str(h.id) for h in hits_raw_a}:
        raise AssertionError("raw search must also filter by client_id")

    result_b = search_knowledge(
        client_id=tenant_b,
        query=secret_b,
        limit=10,
        settings=settings,
        tei=_StubTei(),  # type: ignore[arg-type]
        client=qclient,
    )
    ids_b = {h.point_id for h in result_b.hits}
    if id_b not in ids_b:
        raise AssertionError("tenant B should retrieve its own point")
    if id_a in ids_b:
        raise AssertionError("tenant B must not see tenant A")

    return {
        "mode": mode,
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "point_a": id_a,
        "point_b": id_b,
        "hits_a": len(result_a.hits),
        "hits_b": len(result_b.hits),
        "no_leak": True,
    }

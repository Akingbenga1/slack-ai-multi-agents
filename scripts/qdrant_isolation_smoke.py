"""Sprint 6.3 — Qdrant tenant isolation smoke (raw vectors).

Upserts one point per tenant, searches each, asserts no cross-tenant hits.
"""

from __future__ import annotations

import sys
import uuid

from api.app.qdrant import (
    TenantFilterRequired,
    ensure_knowledge_collection,
    search_vectors,
    upsert_vectors,
)
from api.app.settings import get_settings
from api.app.tei import TeiClient


TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _unit_vector(dim: int, hot_index: int) -> list[float]:
    """Simple orthogonal-ish raw vectors for isolation (no TEI required)."""
    v = [0.0] * dim
    v[hot_index % dim] = 1.0
    return v


def main() -> int:
    settings = get_settings()
    collection = ensure_knowledge_collection(settings=settings)
    print(f"collection={collection} dim={settings.embedding_dim}")

    # Light TEI check (Task 6.2) — not required for isolation math
    tei = TeiClient(settings)
    info = tei.info()
    print(f"tei_model={info.get('model_id')} settings_model={settings.embedding_model_id}")
    sample = tei.embed("sprint 6 tei smoke")
    print(f"tei_embed_ok dim={len(sample[0])}")

    vec_a = _unit_vector(settings.embedding_dim, 0)
    vec_b = _unit_vector(settings.embedding_dim, 1)
    id_a = str(uuid.uuid4())
    id_b = str(uuid.uuid4())

    upsert_vectors(
        client_id=TENANT_A,
        vectors=[vec_a],
        payloads=[{"label": "tenant-a", "smoke": "6.3"}],
        ids=[id_a],
        settings=settings,
    )
    upsert_vectors(
        client_id=TENANT_B,
        vectors=[vec_b],
        payloads=[{"label": "tenant-b", "smoke": "6.3"}],
        ids=[id_b],
        settings=settings,
    )
    print(f"upserted A={id_a} B={id_b}")

    hits_a = search_vectors(client_id=TENANT_A, query_vector=vec_a, limit=10, settings=settings)
    hits_b = search_vectors(client_id=TENANT_B, query_vector=vec_b, limit=10, settings=settings)

    ids_a = {str(h.id) for h in hits_a}
    ids_b = {str(h.id) for h in hits_b}
    print(f"search_A ids={sorted(ids_a)} payloads={[h.payload for h in hits_a]}")
    print(f"search_B ids={sorted(ids_b)} payloads={[h.payload for h in hits_b]}")

    assert id_a in ids_a, "tenant A should retrieve its own point"
    assert id_b not in ids_a, "tenant A must not see tenant B"
    assert id_b in ids_b, "tenant B should retrieve its own point"
    assert id_a not in ids_b, "tenant B must not see tenant A"
    for h in hits_a:
        assert h.payload and h.payload.get("client_id") == TENANT_A
    for h in hits_b:
        assert h.payload and h.payload.get("client_id") == TENANT_B

    try:
        search_vectors(client_id=None, query_vector=vec_a, settings=settings)  # type: ignore[arg-type]
        raise AssertionError("expected TenantFilterRequired for missing client_id")
    except TenantFilterRequired:
        print("fail_closed_ok missing_client_id")

    print("isolation_smoke_ok")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"isolation_smoke_FAILED: {exc}", file=sys.stderr)
        raise

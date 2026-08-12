"""Fail-closed tenant isolation tests for retrieval (Task 10.2 / 35.3)."""

from __future__ import annotations

import pytest

from api.app.qdrant import TenantFilterRequired, search_vectors, upsert_vectors
from api.app.retrieval import search_knowledge
from tests.retrieval.helpers import (
    TENANT_A,
    TENANT_B,
    StubTei,
    memory_client,
    memory_settings,
    memory_store,
    unit_vector,
)


def test_tenant_a_search_never_returns_tenant_b():
    settings = memory_settings()
    client = memory_client()
    store = memory_store(settings, client)
    vec_a = unit_vector(0)
    vec_b = unit_vector(1)
    id_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1"
    id_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1"

    upsert_vectors(
        client_id=TENANT_A,
        vectors=[vec_a],
        payloads=[{"kind": "slack_message", "channel": "CA", "ts": "1.0", "text": "alpha secret"}],
        ids=[id_a],
        client=client,
        settings=settings,
    )
    upsert_vectors(
        client_id=TENANT_B,
        vectors=[vec_b],
        payloads=[{"kind": "slack_message", "channel": "CB", "ts": "2.0", "text": "bravo secret"}],
        ids=[id_b],
        client=client,
        settings=settings,
    )

    # Even if the query embedding matches B's vector, tenant A must not see it.
    tei = StubTei({"bravo": vec_b, "alpha": vec_a}, default=vec_b)
    result_a = search_knowledge(
        client_id=TENANT_A,
        query="bravo secret from other tenant",
        limit=10,
        settings=settings,
        embeddings=tei,
        store=store,
    )
    ids_a = {h.point_id for h in result_a.hits}
    assert id_b not in ids_a
    assert all(h.client_id == TENANT_A for h in result_a.hits)

    result_b = search_knowledge(
        client_id=TENANT_B,
        query="bravo secret",
        limit=10,
        settings=settings,
        embeddings=tei,
        store=store,
    )
    ids_b = {h.point_id for h in result_b.hits}
    assert id_b in ids_b
    assert id_a not in ids_b
    assert all(h.client_id == TENANT_B for h in result_b.hits)


def test_search_vectors_missing_client_id_raises():
    settings = memory_settings()
    client = memory_client()
    with pytest.raises(TenantFilterRequired):
        search_vectors(
            client_id=None,
            query_vector=unit_vector(0),
            client=client,
            settings=settings,
        )
    with pytest.raises(TenantFilterRequired):
        search_vectors(
            client_id="  ",
            query_vector=unit_vector(0),
            client=client,
            settings=settings,
        )


def test_search_knowledge_empty_client_id_raises():
    with pytest.raises(TenantFilterRequired):
        search_knowledge(
            client_id="",
            query="anything",
            settings=memory_settings(),
            embeddings=StubTei({"anything": unit_vector(0)}),
            store=memory_store(),
        )


def test_upsert_rejects_mismatched_payload_client_id():
    settings = memory_settings()
    client = memory_client()
    with pytest.raises(TenantFilterRequired):
        upsert_vectors(
            client_id=TENANT_A,
            vectors=[unit_vector(0)],
            payloads=[{"client_id": TENANT_B, "text": "leak"}],
            client=client,
            settings=settings,
        )

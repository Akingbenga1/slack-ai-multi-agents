"""VectorStore factory smoke (Sprint 35.1)."""

from __future__ import annotations

import pytest

from api.app.qdrant import TenantFilterRequired
from api.app.settings import Settings
from api.app.vector_store import QdrantVectorStore, get_vector_store


def test_factory_defaults_to_qdrant():
    store = get_vector_store(Settings(vector_store="qdrant"))
    assert isinstance(store, QdrantVectorStore)
    assert store.name == "qdrant"


def test_factory_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown VECTOR_STORE"):
        get_vector_store(Settings(vector_store="weaviate"))


def test_factory_pgvector_not_implemented():
    with pytest.raises(ValueError, match="pgvector"):
        get_vector_store(Settings(vector_store="pgvector"))


def test_qdrant_adapter_search_missing_client_id_raises():
    store = QdrantVectorStore(Settings(embedding_dim=3))
    with pytest.raises(TenantFilterRequired):
        store.search(client_id=None, query_vector=[0.0, 0.0, 0.0], ensure_collection=False)


def test_qdrant_adapter_upsert_missing_client_id_raises():
    store = QdrantVectorStore(Settings(embedding_dim=3))
    with pytest.raises(TenantFilterRequired):
        store.upsert(
            client_id="",
            vectors=[[0.0, 0.0, 0.0]],
            ensure_collection=False,
        )

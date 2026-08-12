"""Vector-store Strategy — Qdrant is the first adapter (Sprint 35)."""

from api.app.vector_store.provider import VectorStore, get_vector_store
from api.app.vector_store.qdrant_adapter import QdrantVectorStore
from api.app.vector_store.types import CLIENT_ID_PAYLOAD_KEY, VectorFilters, VectorHit

__all__ = [
    "CLIENT_ID_PAYLOAD_KEY",
    "QdrantVectorStore",
    "VectorFilters",
    "VectorHit",
    "VectorStore",
    "get_vector_store",
]

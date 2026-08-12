"""Embedding Strategy — TEI is the first adapter (Sprint 35)."""

from api.app.embedding.provider import EmbeddingProvider, get_embedding_provider
from api.app.embedding.tei_adapter import TeiEmbeddingProvider

__all__ = [
    "EmbeddingProvider",
    "TeiEmbeddingProvider",
    "get_embedding_provider",
]

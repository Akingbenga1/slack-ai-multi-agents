"""Helpers for retrieval tests — in-memory Qdrant + stub embeddings."""

from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient

from api.app.settings import Settings
from api.app.vector_store import QdrantVectorStore

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "knowledge"
TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
DIM = 8


def memory_settings(**overrides) -> Settings:
    base = {
        "embedding_dim": DIM,
        "qdrant_collection": "knowledge_test",
        "qdrant_url": "http://localhost:6333",
        "tei_url": "http://localhost:8080",
        "vector_store": "qdrant",
        "embedding_provider": "tei",
    }
    base.update(overrides)
    return Settings(**base)


def memory_client() -> QdrantClient:
    return QdrantClient(":memory:")


def memory_store(settings: Settings | None = None, client: QdrantClient | None = None) -> QdrantVectorStore:
    settings = settings or memory_settings()
    return QdrantVectorStore(settings, client=client or memory_client())


def unit_vector(hot_index: int, dim: int = DIM) -> list[float]:
    v = [0.0] * dim
    v[hot_index % dim] = 1.0
    return v


class StubTei:
    """EmbeddingProvider stand-in: maps query substrings to fixed vectors."""

    name = "stub"
    model_id = "stub"
    dim = DIM

    def __init__(
        self,
        mapping: dict[str, list[float]],
        default: list[float] | None = None,
    ):
        self.mapping = mapping
        self.default = default or unit_vector(0)

    def embed(self, texts, *, truncate: bool = True):  # noqa: ARG002
        if isinstance(texts, str):
            return [self._vec(texts)]
        return [self._vec(t) for t in texts]

    def _vec(self, text: str) -> list[float]:
        lowered = text.lower()
        for key, vec in self.mapping.items():
            if key.lower() in lowered:
                return list(vec)
        return list(self.default)

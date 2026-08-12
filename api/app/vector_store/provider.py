"""Vector-store Strategy + Factory (Sprint 35).

Knowledge ingest/retrieve know only ``VectorStore`` — upsert, search,
ensure-collection with fail-closed ``client_id``. Vendor SDKs live in
adapters; ``get_vector_store`` selects by ``VECTOR_STORE``.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from api.app.settings import Settings, get_settings
from api.app.vector_store.types import VectorFilters, VectorHit


class VectorStore(Protocol):
    """Vendor-neutral knowledge vector store."""

    @property
    def name(self) -> str:
        """Adapter id (e.g. ``qdrant``)."""
        ...

    def ensure_collection(self) -> str:
        """Create collection / index if missing; return collection name."""
        ...

    def upsert(
        self,
        *,
        client_id: str | None,
        vectors: Sequence[Sequence[float]],
        payloads: Sequence[Mapping[str, Any]] | None = None,
        ids: Sequence[str | int] | None = None,
        ensure_collection: bool = True,
    ) -> list[str | int]:
        """Upsert points for one tenant. Always scopes by ``client_id``."""
        ...

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
        """Nearest-neighbor search with mandatory tenant filter (fail-closed)."""
        ...


def get_vector_store(settings: Settings | None = None) -> VectorStore:
    """Factory: select vector adapter by ``VECTOR_STORE`` (default ``qdrant``)."""
    settings = settings or get_settings()
    name = (settings.vector_store or "qdrant").strip().lower()
    if name == "qdrant":
        from api.app.vector_store.qdrant_adapter import QdrantVectorStore

        return QdrantVectorStore(settings)
    if name == "pgvector":
        raise ValueError(
            "pgvector vector-store adapter is not implemented — set VECTOR_STORE=qdrant "
            "(documented extension only)"
        )
    raise ValueError(f"Unknown VECTOR_STORE={name!r}; expected qdrant|pgvector")

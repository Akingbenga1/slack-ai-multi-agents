"""Embedding Strategy + Factory (Sprint 35).

Ingest/retrieve know only ``EmbeddingProvider.embed`` — texts → vectors of
configured dim. Vendor HTTP / SDKs live in adapters; ``get_embedding_provider``
selects by ``EMBEDDING_PROVIDER``.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from api.app.settings import Settings, get_settings


class EmbeddingProvider(Protocol):
    """Vendor-neutral text embedding surface."""

    @property
    def name(self) -> str:
        """Adapter id (e.g. ``tei``)."""
        ...

    @property
    def model_id(self) -> str:
        """Adapter-owned model identifier."""
        ...

    @property
    def dim(self) -> int:
        """Configured output vector dimension."""
        ...

    def embed(
        self,
        texts: str | Sequence[str],
        *,
        truncate: bool = True,
    ) -> list[list[float]]:
        """Embed one or more texts; each vector length equals ``dim``."""
        ...


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Factory: select embedder by ``EMBEDDING_PROVIDER`` (default ``tei``)."""
    settings = settings or get_settings()
    name = (settings.embedding_provider or "tei").strip().lower()
    if name == "tei":
        from api.app.embedding.tei_adapter import TeiEmbeddingProvider

        return TeiEmbeddingProvider(settings)
    if name == "ollama":
        raise ValueError(
            "Ollama embedding adapter is not implemented — set EMBEDDING_PROVIDER=tei "
            "(documented extension only)"
        )
    if name == "openai":
        raise ValueError(
            "OpenAI embedding adapter is not implemented — set EMBEDDING_PROVIDER=tei "
            "(documented extension only)"
        )
    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER={name!r}; expected tei|ollama|openai"
    )

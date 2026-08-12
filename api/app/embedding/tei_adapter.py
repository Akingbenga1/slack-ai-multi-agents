"""TEI Adapter for ``EmbeddingProvider`` (Sprint 35).

Owns Hugging Face Text Embeddings Inference via ``TeiClient``.
Dim / model id stay on this adapter (settings secrets unchanged).
"""

from __future__ import annotations

from typing import Sequence

from api.app.settings import Settings, get_settings
from api.app.tei.client import TeiClient


class TeiEmbeddingProvider:
    """TEI ``POST /embed`` adapter."""

    name = "tei"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: TeiClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client or TeiClient(self.settings)

    @property
    def model_id(self) -> str:
        return self._client.model_id

    @property
    def dim(self) -> int:
        return self.settings.embedding_dim

    def embed(
        self,
        texts: str | Sequence[str],
        *,
        truncate: bool = True,
    ) -> list[list[float]]:
        return self._client.embed(texts, truncate=truncate)

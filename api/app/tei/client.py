"""HTTP client for Hugging Face Text Embeddings Inference (TEI)."""

from __future__ import annotations

from typing import Sequence

import httpx

from api.app.http_retry import call_with_retries, is_transient_http_status
from api.app.settings import Settings, get_settings


class TeiError(RuntimeError):
    """TEI request failed or returned an unexpected payload."""


class TeiClient:
    """Embed texts via TEI `POST /embed` using the configured model id."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        max_retries: int = 3,
    ) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.tei_url.rstrip("/")
        self.model_id = self.settings.embedding_model_id
        self.max_retries = max_retries

    def info(self) -> dict:
        def _once() -> dict:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(f"{self.base_url}/info")
                if is_transient_http_status(r.status_code):
                    raise TeiError(f"TEI /info HTTP {r.status_code}: {r.text[:200]}")
                r.raise_for_status()
                return r.json()

        return call_with_retries(
            _once,
            max_retries=self.max_retries,
            should_retry=_tei_should_retry,
            label="tei.info",
        )

    def embed(
        self,
        texts: str | Sequence[str],
        *,
        truncate: bool = True,
    ) -> list[list[float]]:
        if isinstance(texts, str):
            inputs: str | list[str] = texts
            expected = 1
        else:
            batch = [t for t in texts]
            if not batch:
                raise ValueError("texts must be non-empty")
            inputs = batch
            expected = len(batch)

        def _once() -> list[list[float]]:
            with httpx.Client(timeout=60.0) as client:
                r = client.post(
                    f"{self.base_url}/embed",
                    json={"inputs": inputs, "truncate": truncate},
                    headers={"Content-Type": "application/json"},
                )
                if is_transient_http_status(r.status_code):
                    raise TeiError(f"TEI /embed HTTP {r.status_code}: {r.text[:300]}")
                if r.status_code >= 400:
                    raise TeiError(f"TEI /embed HTTP {r.status_code}: {r.text[:300]}")
                data = r.json()

            if not isinstance(data, list) or not data:
                raise TeiError(f"unexpected TEI response type: {type(data)!r}")

            if isinstance(inputs, str):
                if isinstance(data[0], (int, float)):
                    vectors = [list(map(float, data))]
                elif isinstance(data[0], list):
                    vectors = [list(map(float, row)) for row in data]
                else:
                    raise TeiError("unexpected TEI embedding shape for single input")
            else:
                if not all(isinstance(row, list) for row in data):
                    raise TeiError("unexpected TEI embedding shape for batch input")
                vectors = [list(map(float, row)) for row in data]

            if len(vectors) != expected:
                raise TeiError(f"expected {expected} vectors, got {len(vectors)}")

            dim = self.settings.embedding_dim
            for i, vec in enumerate(vectors):
                if len(vec) != dim:
                    raise TeiError(
                        f"vector[{i}] dim {len(vec)} != configured embedding_dim {dim} "
                        f"(model_id={self.model_id!r})"
                    )
            return vectors

        return call_with_retries(
            _once,
            max_retries=self.max_retries,
            should_retry=_tei_should_retry,
            label="tei.embed",
        )


def _tei_should_retry(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, TeiError):
        msg = str(exc)
        return "HTTP 429" in msg or "HTTP 5" in msg
    return False


def embed_texts(
    texts: str | Sequence[str],
    *,
    settings: Settings | None = None,
    truncate: bool = True,
) -> list[list[float]]:
    """Convenience wrapper around `TeiClient.embed`."""
    return TeiClient(settings).embed(texts, truncate=truncate)

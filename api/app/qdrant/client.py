"""Qdrant client factory."""

from __future__ import annotations

from functools import lru_cache

from qdrant_client import QdrantClient

from api.app.settings import Settings, get_settings


@lru_cache
def _client_for_url(url: str) -> QdrantClient:
    # Compose pins qdrant/qdrant:v1.13.2; client may be newer — skip noisy check.
    return QdrantClient(url=url, check_compatibility=False)


def get_qdrant_client(settings: Settings | None = None) -> QdrantClient:
    settings = settings or get_settings()
    return _client_for_url(settings.qdrant_url.rstrip("/"))

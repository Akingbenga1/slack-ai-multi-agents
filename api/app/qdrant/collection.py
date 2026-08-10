"""Ensure the shared knowledge collection and tenant payload index exist."""

from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.http import models

from api.app.qdrant.client import get_qdrant_client
from api.app.settings import Settings, get_settings

CLIENT_ID_PAYLOAD_KEY = "client_id"


def ensure_knowledge_collection(
    *,
    client: QdrantClient | None = None,
    settings: Settings | None = None,
) -> str:
    """Create collection (if missing) and ensure `client_id` keyword index.

    Returns the collection name.
    """
    settings = settings or get_settings()
    client = client or get_qdrant_client(settings)
    name = settings.qdrant_collection

    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=settings.embedding_dim,
                distance=models.Distance.COSINE,
            ),
        )

    _ensure_client_id_index(client, name)
    return name


def _ensure_client_id_index(client: QdrantClient, collection_name: str) -> None:
    info = client.get_collection(collection_name)
    indexes = info.payload_schema or {}
    existing = indexes.get(CLIENT_ID_PAYLOAD_KEY)
    if existing is not None:
        return

    client.create_payload_index(
        collection_name=collection_name,
        field_name=CLIENT_ID_PAYLOAD_KEY,
        field_schema=models.PayloadSchemaType.KEYWORD,
    )

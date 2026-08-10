"""Qdrant knowledge store — mandatory tenant (`client_id`) isolation."""

from api.app.qdrant.client import get_qdrant_client
from api.app.qdrant.collection import CLIENT_ID_PAYLOAD_KEY, ensure_knowledge_collection
from api.app.qdrant.tenant import TenantFilterRequired, require_client_id, tenant_filter
from api.app.qdrant.vectors import search_vectors, upsert_vectors

__all__ = [
    "CLIENT_ID_PAYLOAD_KEY",
    "TenantFilterRequired",
    "ensure_knowledge_collection",
    "get_qdrant_client",
    "require_client_id",
    "search_vectors",
    "tenant_filter",
    "upsert_vectors",
]

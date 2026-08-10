"""Fail-closed tenant filter helpers for Qdrant."""

from __future__ import annotations

from qdrant_client.http import models

from api.app.qdrant.collection import CLIENT_ID_PAYLOAD_KEY


class TenantFilterRequired(ValueError):
    """Raised when a Qdrant helper is called without a tenant `client_id`."""


def require_client_id(client_id: str | None) -> str:
    if client_id is None:
        raise TenantFilterRequired(
            "client_id is required for Qdrant operations (fail-closed)"
        )
    value = str(client_id).strip()
    if not value:
        raise TenantFilterRequired(
            "client_id is required for Qdrant operations (fail-closed)"
        )
    return value


def tenant_filter(client_id: str | None) -> models.Filter:
    """Build a mandatory `client_id` payload pre-filter (fail-closed)."""
    cid = require_client_id(client_id)
    return models.Filter(
        must=[
            models.FieldCondition(
                key=CLIENT_ID_PAYLOAD_KEY,
                match=models.MatchValue(value=cid),
            )
        ]
    )

"""Build citation metadata from Qdrant scored points."""

from __future__ import annotations

from typing import Any, Mapping

from qdrant_client.http import models

from api.app.qdrant.collection import CLIENT_ID_PAYLOAD_KEY
from api.app.retrieval.types import KnowledgeCitation


def citation_from_point(point: models.ScoredPoint) -> KnowledgeCitation:
    """Map a scored Qdrant point to a citation (Slack or document payload)."""
    payload: Mapping[str, Any] = point.payload or {}
    text = _first_str(payload, "text", "message_text", "unit_text") or ""
    kind = _first_str(payload, "kind") or "unknown"
    client_id = _first_str(payload, CLIENT_ID_PAYLOAD_KEY) or ""

    return KnowledgeCitation(
        point_id=str(point.id),
        score=float(point.score) if point.score is not None else 0.0,
        text=text,
        kind=kind,
        client_id=client_id,
        channel=_first_str(payload, "channel"),
        ts=_first_str(payload, "ts"),
        user=_first_str(payload, "user"),
        thread_ts=_first_str(payload, "thread_ts"),
        filename=_first_str(payload, "filename"),
        locator=_first_str(payload, "locator"),
        title=_first_str(payload, "title"),
        source_format=_first_str(payload, "source_format"),
        chunk_index=_as_int(payload.get("chunk_index")),
        payload=dict(payload),
    )


def _first_str(payload: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

"""Build citation metadata from vector-store hits."""

from __future__ import annotations

from typing import Any, Mapping

from api.app.retrieval.types import KnowledgeCitation
from api.app.vector_store.types import CLIENT_ID_PAYLOAD_KEY, VectorHit


def citation_from_hit(hit: VectorHit) -> KnowledgeCitation:
    """Map a scored vector hit to a citation (Slack or document payload)."""
    payload: Mapping[str, Any] = hit.payload or {}
    text = _first_str(payload, "text", "message_text", "unit_text") or ""
    kind = _first_str(payload, "kind") or "unknown"
    client_id = _first_str(payload, CLIENT_ID_PAYLOAD_KEY) or ""

    return KnowledgeCitation(
        point_id=str(hit.id),
        score=float(hit.score),
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


# Backward-compatible alias (legacy scored-point objects → prefer ``citation_from_hit``)
def citation_from_point(point: Any) -> KnowledgeCitation:
    """Deprecated: accept a scored point-like object or ``VectorHit``."""
    if isinstance(point, VectorHit):
        return citation_from_hit(point)
    payload = getattr(point, "payload", None) or {}
    return citation_from_hit(
        VectorHit(
            id=str(getattr(point, "id", "")),
            score=float(getattr(point, "score", 0.0) or 0.0),
            payload=dict(payload),
        )
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

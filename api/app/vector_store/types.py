"""Vendor-neutral vector-store types (Sprint 35)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

# Mandatory tenant payload key on every upsert / search filter (fail-closed).
CLIENT_ID_PAYLOAD_KEY = "client_id"


@dataclass(frozen=True)
class VectorHit:
    """One nearest-neighbor hit with payload (adapter-agnostic)."""

    id: str
    score: float
    payload: dict[str, Any] = field(default_factory=dict)


# Equality payload filters AND'd with the mandatory tenant ``client_id`` filter.
VectorFilters = Mapping[str, str]

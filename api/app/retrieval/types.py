"""Dataclasses for knowledge search results and filters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class KnowledgeSearchFilters:
    """Optional payload filters AND'd with the mandatory tenant filter."""

    kind: str | None = None  # e.g. slack_message | document
    channel: str | None = None
    filename: str | None = None

    @classmethod
    def from_mapping(
        cls, raw: Mapping[str, Any] | None
    ) -> KnowledgeSearchFilters | None:
        if raw is None:
            return None
        kind = _opt_str(raw.get("kind"))
        channel = _opt_str(raw.get("channel"))
        filename = _opt_str(raw.get("filename"))
        if kind is None and channel is None and filename is None:
            return None
        return cls(kind=kind, channel=channel, filename=filename)


@dataclass(frozen=True)
class KnowledgeCitation:
    """One retrieval hit with source metadata for grounded replies."""

    point_id: str
    score: float
    text: str
    kind: str
    client_id: str
    channel: str | None = None
    ts: str | None = None
    user: str | None = None
    thread_ts: str | None = None
    filename: str | None = None
    locator: str | None = None
    title: str | None = None
    source_format: str | None = None
    chunk_index: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def short_label(self) -> str:
        """Human-readable source label for logs / smoke output."""
        if self.kind == "slack_message":
            parts = ["slack"]
            if self.channel:
                parts.append(self.channel)
            if self.ts:
                parts.append(f"ts={self.ts}")
            return " ".join(parts)
        if self.kind == "document":
            parts = ["document"]
            if self.filename:
                parts.append(self.filename)
            if self.locator:
                parts.append(self.locator)
            return " ".join(parts)
        return f"{self.kind} id={self.point_id}"


@dataclass(frozen=True)
class KnowledgeSearchResult:
    client_id: str
    query: str
    hits: list[KnowledgeCitation] = field(default_factory=list)
    limit: int = 0


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

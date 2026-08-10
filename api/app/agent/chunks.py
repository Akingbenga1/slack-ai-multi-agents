"""Serialize retrieval citations for graph state."""

from __future__ import annotations

from typing import Any

from api.app.retrieval.types import KnowledgeCitation


def citation_to_chunk(hit: KnowledgeCitation) -> dict[str, Any]:
    """JSON-serializable chunk payload stored on `AgentState.retrieved_chunks`."""
    return {
        "point_id": hit.point_id,
        "score": hit.score,
        "text": hit.text,
        "kind": hit.kind,
        "client_id": hit.client_id,
        "channel": hit.channel,
        "ts": hit.ts,
        "user": hit.user,
        "thread_ts": hit.thread_ts,
        "filename": hit.filename,
        "locator": hit.locator,
        "title": hit.title,
        "source_format": hit.source_format,
        "chunk_index": hit.chunk_index,
        "label": hit.short_label(),
    }


def _evidence_meta_line(chunk: dict[str, Any]) -> str:
    """Speaker / channel / time line so status & who-said-what can attribute."""
    bits: list[str] = []
    user = chunk.get("user")
    if user:
        bits.append(f"user={user}")
    channel = chunk.get("channel")
    if channel:
        bits.append(f"channel={channel}")
    ts = chunk.get("ts")
    if ts:
        bits.append(f"ts={ts}")
    thread_ts = chunk.get("thread_ts")
    if thread_ts:
        bits.append(f"thread_ts={thread_ts}")
    return " | ".join(bits)


def format_evidence(chunks: list[dict[str, Any]], *, max_chars: int = 6000) -> str:
    """Build a numbered evidence block for the compose prompt."""
    if not chunks:
        return "(no retrieval evidence)"
    parts: list[str] = []
    used = 0
    for i, chunk in enumerate(chunks, start=1):
        label = chunk.get("label") or chunk.get("kind") or f"chunk-{i}"
        text = (chunk.get("text") or "").strip()
        meta = _evidence_meta_line(chunk)
        header = f"[{i}] {label}"
        if meta:
            header = f"{header}\n{meta}"
        block = f"{header}\n{text}"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block) + 2
    return "\n\n".join(parts) if parts else "(no retrieval evidence)"

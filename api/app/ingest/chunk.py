"""Chunk normalized Slack messages into embeddable text units."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from api.app.ingest.schema import NormalizedMessage

# Conservative default for bge-small context; TEI truncate=True is a safety net
DEFAULT_MAX_CHARS = 1500
DEFAULT_OVERLAP = 100


@dataclass(frozen=True)
class MessageChunk:
    """One embeddable unit derived from a NormalizedMessage."""

    message: NormalizedMessage
    chunk_index: int
    chunk_count: int
    text: str
    content_hash: str

    @property
    def content_key(self) -> str:
        return self.message.content_key


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def format_chunk_text(message: NormalizedMessage, body: str) -> str:
    """Prefix metadata so retrieval can surface channel/user context."""
    parts = [f"channel={message.channel}"]
    if message.user:
        parts.append(f"user={message.user}")
    parts.append(f"ts={message.ts}")
    if message.thread_ts:
        parts.append(f"thread_ts={message.thread_ts}")
    header = " ".join(parts)
    return f"{header}\n{body}"


def _split_body(body: str, *, max_chars: int, overlap: int) -> list[str]:
    if len(body) <= max_chars:
        return [body]
    if overlap >= max_chars:
        overlap = max(0, max_chars // 5)
    pieces: list[str] = []
    start = 0
    n = len(body)
    while start < n:
        end = min(start + max_chars, n)
        pieces.append(body[start:end])
        if end >= n:
            break
        start = max(0, end - overlap)
    return pieces


def chunk_message(
    message: NormalizedMessage,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[MessageChunk]:
    """Split one message into one or more chunks (usually a single chunk)."""
    bodies = _split_body(message.text, max_chars=max_chars, overlap=overlap)
    count = len(bodies)
    out: list[MessageChunk] = []
    for i, body in enumerate(bodies):
        text = format_chunk_text(message, body)
        out.append(
            MessageChunk(
                message=message,
                chunk_index=i,
                chunk_count=count,
                text=text,
                content_hash=content_hash(text),
            )
        )
    return out


def chunk_messages(
    messages: list[NormalizedMessage] | tuple[NormalizedMessage, ...],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[MessageChunk]:
    chunks: list[MessageChunk] = []
    for msg in messages:
        chunks.extend(chunk_message(msg, max_chars=max_chars, overlap=overlap))
    return chunks

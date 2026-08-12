"""Chunk → embed → vector-store ingest for normalized Slack history."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from api.app.embedding import EmbeddingProvider
from api.app.ingest.chunk import MessageChunk, chunk_messages
from api.app.ingest.chunks_ingest import DEFAULT_EMBED_BATCH, ingest_chunks
from api.app.ingest.schema import NormalizedMessage
from api.app.settings import Settings
from api.app.vector_store import VectorStore

__all__ = [
    "DEFAULT_EMBED_BATCH",
    "IngestResult",
    "chunk_payload",
    "ingest_messages",
    "point_id_for_chunk",
]


def point_id_for_chunk(client_id: str, chunk: MessageChunk) -> str:
    """
    Deterministic knowledge point UUID (uuid5) for idempotent upserts.

    Keyed by tenant + channel + ts + chunk_index (not content hash), so
    re-ingest of the same message overwrites the same points.
    """
    key = (
        f"slack-history|{client_id}|{chunk.message.channel}|"
        f"{chunk.message.ts}|{chunk.chunk_index}"
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def chunk_payload(chunk: MessageChunk) -> dict:
    msg = chunk.message
    return {
        "kind": "slack_message",
        "channel": msg.channel,
        "ts": msg.ts,
        "user": msg.user,
        "thread_ts": msg.thread_ts,
        "source_format": str(msg.source_format),
        "text": chunk.text,
        "message_text": msg.text,
        "chunk_index": chunk.chunk_index,
        "chunk_count": chunk.chunk_count,
        "content_key": chunk.content_key,
        "content_hash": chunk.content_hash,
    }


@dataclass
class IngestResult:
    client_id: str
    message_count: int
    chunk_count: int
    point_ids: list[str] = field(default_factory=list)


def ingest_messages(
    *,
    client_id: str,
    messages: Sequence[NormalizedMessage] | Iterable[NormalizedMessage],
    settings: Settings | None = None,
    embeddings: EmbeddingProvider | None = None,
    store: VectorStore | None = None,
    embed_batch_size: int = DEFAULT_EMBED_BATCH,
    max_chars: int = 1500,
    overlap: int = 100,
) -> IngestResult:
    """
    Chunk messages, embed, upsert into the knowledge collection.

    Requires a non-empty ``client_id`` (fail-closed at the vector store).
    """
    msg_list = list(messages)
    chunks = chunk_messages(msg_list, max_chars=max_chars, overlap=overlap)
    if not chunks:
        return IngestResult(client_id=client_id, message_count=0, chunk_count=0)

    point_ids = ingest_chunks(
        client_id=client_id,
        chunks=chunks,
        point_id_fn=point_id_for_chunk,
        payload_fn=chunk_payload,
        settings=settings,
        embeddings=embeddings,
        store=store,
        embed_batch_size=embed_batch_size,
    )
    return IngestResult(
        client_id=client_id,
        message_count=len(msg_list),
        chunk_count=len(chunks),
        point_ids=point_ids,
    )

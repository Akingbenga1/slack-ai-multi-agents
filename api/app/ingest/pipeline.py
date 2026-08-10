"""Chunk → TEI → Qdrant ingest for normalized Slack history."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from api.app.ingest.chunk import MessageChunk, chunk_messages
from api.app.ingest.schema import NormalizedMessage
from api.app.qdrant.vectors import upsert_vectors
from api.app.settings import Settings, get_settings
from api.app.tei.client import TeiClient

DEFAULT_EMBED_BATCH = 32


def point_id_for_chunk(client_id: str, chunk: MessageChunk) -> str:
    """
    Deterministic Qdrant point UUID (uuid5) for idempotent upserts.

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
    tei: TeiClient | None = None,
    embed_batch_size: int = DEFAULT_EMBED_BATCH,
    max_chars: int = 1500,
    overlap: int = 100,
) -> IngestResult:
    """
    Chunk messages, embed via TEI, upsert into the knowledge collection.

    Requires a non-empty ``client_id`` (fail-closed at Qdrant helpers).
    """
    settings = settings or get_settings()
    tei = tei or TeiClient(settings)
    msg_list = list(messages)
    chunks = chunk_messages(msg_list, max_chars=max_chars, overlap=overlap)
    if not chunks:
        return IngestResult(client_id=client_id, message_count=0, chunk_count=0)

    point_ids: list[str] = []
    batch_size = max(1, embed_batch_size)
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors = tei.embed([c.text for c in batch])
        ids = [point_id_for_chunk(client_id, c) for c in batch]
        payloads = [chunk_payload(c) for c in batch]
        upsert_vectors(
            client_id=client_id,
            vectors=vectors,
            payloads=payloads,
            ids=ids,
            settings=settings,
        )
        point_ids.extend(ids)

    return IngestResult(
        client_id=client_id,
        message_count=len(msg_list),
        chunk_count=len(chunks),
        point_ids=point_ids,
    )

"""Chunk → embed → vector-store ingest for extracted documents."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from api.app.embedding import EmbeddingProvider
from api.app.ingest.chunks_ingest import DEFAULT_EMBED_BATCH, ingest_chunks
from api.app.ingest.document_chunk import DocumentChunk, chunk_document_units
from api.app.ingest.documents.schema import DocumentUnit, ExtractedDocument
from api.app.settings import Settings
from api.app.vector_store import VectorStore

__all__ = [
    "DEFAULT_EMBED_BATCH",
    "DocumentIngestResult",
    "document_chunk_payload",
    "ingest_document_units",
    "ingest_extracted_document",
    "point_id_for_document_chunk",
]


def point_id_for_document_chunk(client_id: str, chunk: DocumentChunk) -> str:
    """Deterministic uuid5 for idempotent document upserts."""
    unit = chunk.unit
    key = (
        f"document|{client_id}|{unit.filename or '_'}|{unit.locator}|{chunk.chunk_index}"
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def document_chunk_payload(chunk: DocumentChunk) -> dict:
    unit = chunk.unit
    return {
        "kind": "document",
        "source_format": str(unit.source_format),
        "unit_kind": str(unit.kind),
        "locator": unit.locator,
        "filename": unit.filename,
        "title": unit.title,
        "text": chunk.text,
        "unit_text": unit.text,
        "chunk_index": chunk.chunk_index,
        "chunk_count": chunk.chunk_count,
        "content_key": chunk.content_key,
        "content_hash": chunk.content_hash,
    }


@dataclass
class DocumentIngestResult:
    client_id: str
    unit_count: int
    chunk_count: int
    point_ids: list[str] = field(default_factory=list)


def ingest_document_units(
    *,
    client_id: str,
    units: Sequence[DocumentUnit] | Iterable[DocumentUnit],
    settings: Settings | None = None,
    embeddings: EmbeddingProvider | None = None,
    store: VectorStore | None = None,
    embed_batch_size: int = DEFAULT_EMBED_BATCH,
    max_chars: int = 1500,
    overlap: int = 100,
) -> DocumentIngestResult:
    unit_list = list(units)
    chunks = chunk_document_units(unit_list, max_chars=max_chars, overlap=overlap)
    if not chunks:
        return DocumentIngestResult(client_id=client_id, unit_count=0, chunk_count=0)

    point_ids = ingest_chunks(
        client_id=client_id,
        chunks=chunks,
        point_id_fn=point_id_for_document_chunk,
        payload_fn=document_chunk_payload,
        settings=settings,
        embeddings=embeddings,
        store=store,
        embed_batch_size=embed_batch_size,
    )
    return DocumentIngestResult(
        client_id=client_id,
        unit_count=len(unit_list),
        chunk_count=len(chunks),
        point_ids=point_ids,
    )


def ingest_extracted_document(
    *,
    client_id: str,
    document: ExtractedDocument,
    settings: Settings | None = None,
    embeddings: EmbeddingProvider | None = None,
    store: VectorStore | None = None,
) -> DocumentIngestResult:
    return ingest_document_units(
        client_id=client_id,
        units=document.units,
        settings=settings,
        embeddings=embeddings,
        store=store,
    )

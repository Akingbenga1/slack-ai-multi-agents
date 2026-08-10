"""Chunk → TEI → Qdrant ingest for extracted documents."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from api.app.ingest.document_chunk import DocumentChunk, chunk_document_units
from api.app.ingest.documents.schema import DocumentUnit, ExtractedDocument
from api.app.qdrant.vectors import upsert_vectors
from api.app.settings import Settings, get_settings
from api.app.tei.client import TeiClient

DEFAULT_EMBED_BATCH = 32


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
    tei: TeiClient | None = None,
    embed_batch_size: int = DEFAULT_EMBED_BATCH,
    max_chars: int = 1500,
    overlap: int = 100,
) -> DocumentIngestResult:
    settings = settings or get_settings()
    tei = tei or TeiClient(settings)
    unit_list = list(units)
    chunks = chunk_document_units(unit_list, max_chars=max_chars, overlap=overlap)
    if not chunks:
        return DocumentIngestResult(client_id=client_id, unit_count=0, chunk_count=0)

    point_ids: list[str] = []
    batch_size = max(1, embed_batch_size)
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors = tei.embed([c.text for c in batch])
        ids = [point_id_for_document_chunk(client_id, c) for c in batch]
        payloads = [document_chunk_payload(c) for c in batch]
        upsert_vectors(
            client_id=client_id,
            vectors=vectors,
            payloads=payloads,
            ids=ids,
            settings=settings,
        )
        point_ids.extend(ids)

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
    tei: TeiClient | None = None,
) -> DocumentIngestResult:
    return ingest_document_units(
        client_id=client_id,
        units=document.units,
        settings=settings,
        tei=tei,
    )

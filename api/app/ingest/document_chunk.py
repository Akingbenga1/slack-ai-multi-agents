"""Chunk extracted document units into embeddable text."""

from __future__ import annotations

from dataclasses import dataclass

from api.app.ingest.chunk import DEFAULT_MAX_CHARS, DEFAULT_OVERLAP, _split_body, content_hash
from api.app.ingest.documents.schema import DocumentUnit


@dataclass(frozen=True)
class DocumentChunk:
    unit: DocumentUnit
    chunk_index: int
    chunk_count: int
    text: str
    content_hash: str

    @property
    def content_key(self) -> str:
        return f"{self.unit.content_key}#{self.chunk_index}"


def format_document_chunk_text(unit: DocumentUnit, body: str) -> str:
    parts = [f"kind=document", f"format={unit.source_format}"]
    if unit.filename:
        parts.append(f"file={unit.filename}")
    if unit.title:
        parts.append(f"title={unit.title}")
    parts.append(f"locator={unit.locator}")
    header = " ".join(parts)
    return f"{header}\n{body}"


def chunk_document_unit(
    unit: DocumentUnit,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[DocumentChunk]:
    bodies = _split_body(unit.text, max_chars=max_chars, overlap=overlap)
    count = len(bodies)
    out: list[DocumentChunk] = []
    for i, body in enumerate(bodies):
        text = format_document_chunk_text(unit, body)
        out.append(
            DocumentChunk(
                unit=unit,
                chunk_index=i,
                chunk_count=count,
                text=text,
                content_hash=content_hash(text),
            )
        )
    return out


def chunk_document_units(
    units: list[DocumentUnit] | tuple[DocumentUnit, ...],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for unit in units:
        chunks.extend(chunk_document_unit(unit, max_chars=max_chars, overlap=overlap))
    return chunks

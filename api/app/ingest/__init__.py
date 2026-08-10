"""Slack history / document ingest — shared schema + format parsers."""

from api.app.ingest.chunk import MessageChunk, chunk_message, chunk_messages
from api.app.ingest.chunks_ingest import DEFAULT_EMBED_BATCH, ingest_chunks
from api.app.ingest.document_pipeline import (
    DocumentIngestResult,
    ingest_document_units,
    ingest_extracted_document,
    point_id_for_document_chunk,
)
from api.app.ingest.documents import (
    DocumentFormat,
    DocumentUnit,
    ExtractedDocument,
    UnsupportedDocumentFormatError,
    extract_document,
)
from api.app.ingest.normalize import normalize_slack_message
from api.app.ingest.pipeline import IngestResult, ingest_messages, point_id_for_chunk
from api.app.ingest.schema import NormalizedMessage, SourceFormat
from api.app.ingest.upload_ingest import UploadIngestResult, ingest_upload

__all__ = [
    "DEFAULT_EMBED_BATCH",
    "DocumentFormat",
    "DocumentIngestResult",
    "DocumentUnit",
    "ExtractedDocument",
    "IngestResult",
    "MessageChunk",
    "NormalizedMessage",
    "SourceFormat",
    "UnsupportedDocumentFormatError",
    "UploadIngestResult",
    "chunk_message",
    "chunk_messages",
    "extract_document",
    "ingest_chunks",
    "ingest_document_units",
    "ingest_extracted_document",
    "ingest_messages",
    "ingest_upload",
    "normalize_slack_message",
    "point_id_for_chunk",
    "point_id_for_document_chunk",
]

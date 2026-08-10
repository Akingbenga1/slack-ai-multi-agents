"""Dispatch document extraction by format / filename extension."""

from __future__ import annotations

from pathlib import Path

from api.app.ingest.documents._io import Readable, normalize_filename
from api.app.ingest.documents.docx import extract_docx
from api.app.ingest.documents.pdf import extract_pdf
from api.app.ingest.documents.schema import DocumentFormat, ExtractedDocument
from api.app.ingest.documents.tabular import extract_csv, extract_xlsx


def _filename_from_source(source: object, filename: str | None) -> str | None:
    name = normalize_filename(filename)
    if name:
        return name
    if isinstance(source, Path):
        return normalize_filename(source.name)
    if isinstance(source, str) and "\n" not in source:
        return normalize_filename(source)
    return None

_EXT_TO_FORMAT: dict[str, DocumentFormat] = {
    ".pdf": DocumentFormat.PDF,
    ".docx": DocumentFormat.DOCX,
    ".xlsx": DocumentFormat.XLSX,
    ".csv": DocumentFormat.CSV,
}

_MIME_TO_FORMAT: dict[str, DocumentFormat] = {
    "application/pdf": DocumentFormat.PDF,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocumentFormat.DOCX,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": DocumentFormat.XLSX,
    "text/csv": DocumentFormat.CSV,
    "application/csv": DocumentFormat.CSV,
}


class UnsupportedDocumentFormatError(ValueError):
    """Raised when format cannot be inferred or is not supported."""


def detect_document_format(
    *,
    filename: str | None = None,
    content_type: str | None = None,
    format: DocumentFormat | str | None = None,
) -> DocumentFormat:
    """Resolve format from explicit value, MIME type, or file extension."""
    if format is not None:
        if isinstance(format, DocumentFormat):
            return format
        try:
            return DocumentFormat(str(format).strip().lower())
        except ValueError as exc:
            raise UnsupportedDocumentFormatError(
                f"Unsupported document format: {format!r}"
            ) from exc

    if content_type:
        mime = content_type.split(";", 1)[0].strip().lower()
        if mime in _MIME_TO_FORMAT:
            return _MIME_TO_FORMAT[mime]

    name = normalize_filename(filename)
    if name:
        ext = Path(name).suffix.lower()
        if ext in _EXT_TO_FORMAT:
            return _EXT_TO_FORMAT[ext]

    raise UnsupportedDocumentFormatError(
        "Could not detect document format; pass format= or a filename "
        "with extension .pdf / .docx / .xlsx / .csv"
    )


def extract_document(
    source: Readable | str,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    format: DocumentFormat | str | None = None,
) -> ExtractedDocument:
    """
    Extract text/table units from a PDF, DOCX, XLSX, or CSV document.

    This is for ``file_role=document`` uploads — Slack history dumps use the
    message parsers under ``api.app.ingest.parsers``.
    """
    name = _filename_from_source(source, filename)
    resolved = detect_document_format(
        filename=name,
        content_type=content_type,
        format=format,
    )

    if resolved is DocumentFormat.PDF:
        return extract_pdf(source, filename=name)  # type: ignore[arg-type]
    if resolved is DocumentFormat.DOCX:
        return extract_docx(source, filename=name)  # type: ignore[arg-type]
    if resolved is DocumentFormat.XLSX:
        return extract_xlsx(source, filename=name)  # type: ignore[arg-type]
    if resolved is DocumentFormat.CSV:
        return extract_csv(source, filename=name)

    raise UnsupportedDocumentFormatError(f"Unsupported document format: {resolved}")

"""PDF text extraction (per page) via pypdf."""

from __future__ import annotations

from pypdf import PdfReader

from api.app.ingest.documents._io import Readable, as_binary_buffer, normalize_filename
from api.app.ingest.documents.schema import (
    DocumentFormat,
    DocumentUnit,
    DocumentUnitKind,
    ExtractedDocument,
)


def extract_pdf(
    source: Readable,
    *,
    filename: str | None = None,
) -> ExtractedDocument:
    """
    Extract plain text from each PDF page.

    Empty pages are skipped. A PDF with no extractable text returns zero units
    (caller may treat that as a soft failure).
    """
    name = normalize_filename(filename)
    if name is None and isinstance(source, str):
        name = normalize_filename(source)

    reader = PdfReader(as_binary_buffer(source))
    title: str | None = None
    meta = getattr(reader, "metadata", None)
    if meta is not None:
        raw_title = getattr(meta, "title", None)
        if raw_title:
            title = str(raw_title).strip() or None

    units: list[DocumentUnit] = []
    for page_index, page in enumerate(reader.pages):
        try:
            raw = page.extract_text() or ""
        except Exception:
            raw = ""
        text = "\n".join(line.strip() for line in raw.splitlines()).strip()
        if not text:
            continue
        page_num = page_index + 1
        units.append(
            DocumentUnit(
                text=text,
                unit_index=len(units),
                source_format=DocumentFormat.PDF,
                kind=DocumentUnitKind.PAGE,
                locator=f"page={page_num}",
                filename=name,
                title=title,
            )
        )

    return ExtractedDocument(
        source_format=DocumentFormat.PDF,
        filename=name,
        title=title,
        units=units,
    )

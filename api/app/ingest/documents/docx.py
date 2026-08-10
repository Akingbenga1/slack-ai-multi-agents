"""DOCX paragraph + table extraction via python-docx."""

from __future__ import annotations

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from api.app.ingest.documents._io import Readable, as_binary_buffer, normalize_filename
from api.app.ingest.documents.schema import (
    DocumentFormat,
    DocumentUnit,
    DocumentUnitKind,
    ExtractedDocument,
)


def _cell_text(cell: object) -> str:
    parts: list[str] = []
    for paragraph in getattr(cell, "paragraphs", []) or []:
        t = (paragraph.text or "").strip()
        if t:
            parts.append(t)
    return " | ".join(parts)


def _table_to_text(table: Table) -> str:
    rows: list[str] = []
    for row in table.rows:
        cells = [_cell_text(c) for c in row.cells]
        # Skip fully empty rows
        if not any(cells):
            continue
        rows.append(" | ".join(cells))
    return "\n".join(rows).strip()


def _iter_block_items(document: Document):
    """Yield paragraphs and tables in document body order."""
    body = document.element.body
    for child in body.iterchildren():
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "p":
            yield Paragraph(child, document)
        elif tag == "tbl":
            yield Table(child, document)


def extract_docx(
    source: Readable,
    *,
    filename: str | None = None,
) -> ExtractedDocument:
    """
    Extract paragraphs and tables from a .docx file in reading order.

    Empty paragraphs are skipped. Tables become single units (pipe-separated cells).
    """
    name = normalize_filename(filename)
    if name is None and isinstance(source, str):
        name = normalize_filename(source)

    document = Document(as_binary_buffer(source))
    core = document.core_properties
    title = (core.title or "").strip() or None

    units: list[DocumentUnit] = []
    para_n = 0
    table_n = 0

    for block in _iter_block_items(document):
        if isinstance(block, Paragraph):
            text = (block.text or "").strip()
            if not text:
                continue
            para_n += 1
            units.append(
                DocumentUnit(
                    text=text,
                    unit_index=len(units),
                    source_format=DocumentFormat.DOCX,
                    kind=DocumentUnitKind.PARAGRAPH,
                    locator=f"paragraph={para_n}",
                    filename=name,
                    title=title,
                )
            )
        elif isinstance(block, Table):
            text = _table_to_text(block)
            if not text:
                continue
            table_n += 1
            units.append(
                DocumentUnit(
                    text=text,
                    unit_index=len(units),
                    source_format=DocumentFormat.DOCX,
                    kind=DocumentUnitKind.TABLE,
                    locator=f"table={table_n}",
                    filename=name,
                    title=title,
                )
            )

    return ExtractedDocument(
        source_format=DocumentFormat.DOCX,
        filename=name,
        title=title,
        units=units,
    )

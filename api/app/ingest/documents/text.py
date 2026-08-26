"""Markdown and plain-text document extraction."""

from __future__ import annotations

import re
from pathlib import Path

from api.app.ingest.documents._io import Readable, normalize_filename, read_bytes
from api.app.ingest.documents.schema import (
    DocumentFormat,
    DocumentUnit,
    DocumentUnitKind,
    ExtractedDocument,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _decode_text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def _title_from_markdown(text: str, filename: str | None) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _HEADING_RE.match(stripped)
        if match:
            return match.group(2).strip() or None
        # First non-empty line as fallback title for plain-ish md
        return stripped[:200] or None
    if filename:
        return Path(filename).stem or None
    return None


def _split_markdown_sections(text: str) -> list[str]:
    """Split on ATX headings; keep heading line with following body."""
    lines = text.split("\n")
    sections: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        if _HEADING_RE.match(line.strip()) and current:
            sections.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append(current)

    out: list[str] = []
    for block in sections:
        body = "\n".join(block).strip()
        if body:
            out.append(body)
    return out


def _split_plain_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def extract_markdown(
    source: Readable,
    *,
    filename: str | None = None,
) -> ExtractedDocument:
    """
    Extract embeddable units from a Markdown file.

    Splits on ATX headings (``#`` … ``######``). Files with no headings become
    one or more blank-line paragraphs.
    """
    name = normalize_filename(filename)
    if name is None and isinstance(source, str) and "\n" not in source:
        name = normalize_filename(source)

    text = _decode_text(read_bytes(source)).strip()
    title = _title_from_markdown(text, name) if text else None

    if not text:
        return ExtractedDocument(
            source_format=DocumentFormat.MD,
            filename=name,
            title=title,
            units=[],
        )

    sections = _split_markdown_sections(text)
    if len(sections) <= 1 and not any(
        _HEADING_RE.match(line.strip()) for line in text.splitlines()
    ):
        sections = _split_plain_paragraphs(text) or [text]

    units: list[DocumentUnit] = []
    for idx, section in enumerate(sections, start=1):
        units.append(
            DocumentUnit(
                text=section,
                unit_index=len(units),
                source_format=DocumentFormat.MD,
                kind=DocumentUnitKind.PARAGRAPH,
                locator=f"section={idx}",
                filename=name,
                title=title,
            )
        )

    return ExtractedDocument(
        source_format=DocumentFormat.MD,
        filename=name,
        title=title,
        units=units,
    )


def extract_txt(
    source: Readable,
    *,
    filename: str | None = None,
) -> ExtractedDocument:
    """Extract embeddable units from a plain-text file (blank-line paragraphs)."""
    name = normalize_filename(filename)
    if name is None and isinstance(source, str) and "\n" not in source:
        name = normalize_filename(source)

    text = _decode_text(read_bytes(source)).strip()
    title = Path(name).stem if name else None

    if not text:
        return ExtractedDocument(
            source_format=DocumentFormat.TXT,
            filename=name,
            title=title,
            units=[],
        )

    paragraphs = _split_plain_paragraphs(text) or [text]
    units: list[DocumentUnit] = []
    for idx, para in enumerate(paragraphs, start=1):
        units.append(
            DocumentUnit(
                text=para,
                unit_index=len(units),
                source_format=DocumentFormat.TXT,
                kind=DocumentUnitKind.PARAGRAPH,
                locator=f"paragraph={idx}",
                filename=name,
                title=title,
            )
        )

    return ExtractedDocument(
        source_format=DocumentFormat.TXT,
        filename=name,
        title=title,
        units=units,
    )

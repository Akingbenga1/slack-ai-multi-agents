"""Shared schema for non-Slack document text/table extraction."""

from __future__ import annotations

from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class DocumentFormat(StrEnum):
    """Supported org-uploaded document formats (Sprint 8+)."""

    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    CSV = "csv"
    MD = "md"
    TXT = "txt"


class DocumentUnitKind(StrEnum):
    PAGE = "page"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    TABLE_ROW = "table_row"
    SHEET = "sheet"


class DocumentUnit(BaseModel):
    """One embeddable text/table unit extracted from a document."""

    text: str = Field(..., min_length=1)
    unit_index: int = Field(..., ge=0)
    source_format: DocumentFormat
    kind: DocumentUnitKind
    locator: str = Field(
        ...,
        min_length=1,
        description="Stable position hint, e.g. page=1, sheet=Orders!row=3",
    )
    filename: Optional[str] = None
    title: Optional[str] = None

    @field_validator("text", "locator", mode="before")
    @classmethod
    def _strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("filename", "title", mode="before")
    @classmethod
    def _strip_optional(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @property
    def content_key(self) -> str:
        """Stable id within a file (format + locator)."""
        name = self.filename or "_"
        return f"{name}:{self.source_format}:{self.locator}"


class ExtractedDocument(BaseModel):
    """Full extraction result for one uploaded file."""

    source_format: DocumentFormat
    filename: Optional[str] = None
    title: Optional[str] = None
    units: list[DocumentUnit] = Field(default_factory=list)

    @property
    def text(self) -> str:
        """Concatenate all unit texts (useful for smoke checks)."""
        return "\n\n".join(u.text for u in self.units)

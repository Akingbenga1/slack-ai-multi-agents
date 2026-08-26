"""Non-Slack document text/table extraction (PDF, DOCX, XLSX, CSV, MD, TXT)."""

from api.app.ingest.documents.docx import extract_docx
from api.app.ingest.documents.extract import (
    UnsupportedDocumentFormatError,
    detect_document_format,
    extract_document,
)
from api.app.ingest.documents.pdf import extract_pdf
from api.app.ingest.documents.schema import (
    DocumentFormat,
    DocumentUnit,
    DocumentUnitKind,
    ExtractedDocument,
)
from api.app.ingest.documents.tabular import extract_csv, extract_xlsx
from api.app.ingest.documents.text import extract_markdown, extract_txt

__all__ = [
    "DocumentFormat",
    "DocumentUnit",
    "DocumentUnitKind",
    "ExtractedDocument",
    "UnsupportedDocumentFormatError",
    "detect_document_format",
    "extract_csv",
    "extract_document",
    "extract_docx",
    "extract_markdown",
    "extract_pdf",
    "extract_txt",
    "extract_xlsx",
]

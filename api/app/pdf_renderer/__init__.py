"""PDF-renderer Strategy — fpdf2 is the first adapter (Sprint 37)."""

from api.app.pdf_renderer.fpdf2_adapter import Fpdf2PdfRenderer
from api.app.pdf_renderer.provider import PdfRenderer, default_pdf_renderer

__all__ = [
    "Fpdf2PdfRenderer",
    "PdfRenderer",
    "default_pdf_renderer",
]

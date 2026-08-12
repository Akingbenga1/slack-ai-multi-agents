"""PDF-renderer Strategy (Sprint 37).

Product code asks for ``title + body → PDF bytes``. Vendor libraries live in
adapters. No Factory this sprint — fpdf2 is the only renderer (adding
``PDF_RENDERER`` only when a second backend is env-selected).
"""

from __future__ import annotations

from typing import Protocol


class PdfRenderer(Protocol):
    """Vendor-neutral PDF bytes from title + body."""

    @property
    def name(self) -> str:
        """Adapter id (e.g. ``fpdf2``)."""
        ...

    def render(
        self,
        *,
        title: str,
        body: str,
        subtitle: str | None = None,
    ) -> bytes:
        """Render a simple multi-page PDF; return raw PDF bytes."""
        ...


def default_pdf_renderer() -> PdfRenderer:
    """Composition root for the single fpdf2 product — not an env Factory.

    Add ``PDF_RENDERER`` + ``get_pdf_renderer(settings)`` only when a second
    backend is env-selected.
    """
    from api.app.pdf_renderer.fpdf2_adapter import Fpdf2PdfRenderer

    return Fpdf2PdfRenderer()

"""Generate PDF deliverables from analysis text (Sprint 23.3 / 37).

Product facade: title + body → PDF bytes via ``PdfRenderer``. fpdf2 is the
first adapter (``api.app.pdf_renderer``); callers must not import fpdf2.
"""

from __future__ import annotations

from pathlib import Path

from api.app.pdf_renderer import PdfRenderer, default_pdf_renderer
from api.app.uploads.storage import sanitize_filename

_DEFAULT_RENDERER: PdfRenderer = default_pdf_renderer()


def sanitize_pdf_stem(name: str) -> str:
    """Stem for PDF filenames — reuses uploads ``sanitize_filename`` alphabet."""
    raw = (name or "").strip()
    if not raw:
        return "analysis"
    stem_raw = Path(raw).stem.strip() or "analysis"
    cleaned = sanitize_filename(stem_raw)
    stem = Path(cleaned).stem.strip("._") or "analysis"
    return stem[:80]


def analysis_to_pdf_bytes(
    *,
    title: str,
    body: str,
    subtitle: str | None = None,
    renderer: PdfRenderer | None = None,
) -> bytes:
    """
    Render a simple multi-page PDF from plain/Slack-ish markdown-ish text.

    Strips common Slack emphasis markers; wraps long lines. Unicode outside
    Latin-1 is replaced so the built-in Helvetica core font stays usable
    (fpdf2 adapter).
    """
    r = renderer or _DEFAULT_RENDERER
    return r.render(title=title, body=body, subtitle=subtitle)


def default_pdf_filename(*, source_filename: str | None = None, prefix: str = "analysis") -> str:
    if source_filename:
        return f"{prefix}_{sanitize_pdf_stem(source_filename)}.pdf"
    return f"{prefix}.pdf"

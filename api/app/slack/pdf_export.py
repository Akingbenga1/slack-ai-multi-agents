"""Generate PDF deliverables from analysis text (Sprint 23.3).

Library: **fpdf2** (lightweight pure-Python PDF writer). Chosen over ReportLab
for a smaller dependency surface on the laptop-VPS demo stack.
"""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

from fpdf import FPDF

from api.app.logging_config import get_logger
from api.app.uploads.storage import sanitize_filename

logger = get_logger("api.slack.pdf_export")


class _AnalysisPDF(FPDF):
    def footer(self) -> None:  # noqa: D401 — fpdf hook
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


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
) -> bytes:
    """
    Render a simple multi-page PDF from plain/Slack-ish markdown-ish text.

    Strips common Slack emphasis markers; wraps long lines. Unicode outside
    Latin-1 is replaced so the built-in Helvetica core font stays usable.
    """
    pdf = _AnalysisPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 9, _latin1(title.strip() or "Analysis"))
    pdf.ln(2)
    if subtitle:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 6, _latin1(subtitle.strip()))
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    pdf.set_font("Helvetica", size=11)
    for paragraph in _paragraphs(body):
        pdf.multi_cell(0, 6, _latin1(paragraph))
        pdf.ln(3)

    buf = BytesIO()
    pdf.output(buf)
    data = buf.getvalue()
    logger.info("pdf_export_ok bytes=%s title=%s", len(data), title[:60])
    return data


def default_pdf_filename(*, source_filename: str | None = None, prefix: str = "analysis") -> str:
    if source_filename:
        return f"{prefix}_{sanitize_pdf_stem(source_filename)}.pdf"
    return f"{prefix}.pdf"


def _paragraphs(body: str) -> list[str]:
    raw = (body or "").replace("\r\n", "\n").strip()
    if not raw:
        return ["(empty analysis)"]
    # Soft-strip Slack mrkdwn
    cleaned = raw.replace("*", "").replace("_", "").replace("`", "")
    parts = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
    return parts or [cleaned]


def _latin1(text: str) -> str:
    return (text or "").encode("latin-1", errors="replace").decode("latin-1")

"""fpdf2 Adapter for ``PdfRenderer`` (Sprint 37).

Owns ``fpdf`` / ``FPDF``. Chosen over ReportLab for a smaller dependency
surface on the laptop-VPS demo stack.
"""

from __future__ import annotations

import re
from io import BytesIO

from fpdf import FPDF

from api.app.logging_config import get_logger

logger = get_logger("api.pdf_renderer.fpdf2")


class _AnalysisPDF(FPDF):
    def footer(self) -> None:  # noqa: D401 — fpdf hook
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


class Fpdf2PdfRenderer:
    """fpdf2 title + body → PDF bytes adapter."""

    name = "fpdf2"

    def render(
        self,
        *,
        title: str,
        body: str,
        subtitle: str | None = None,
    ) -> bytes:
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
        logger.info("pdf_render_ok bytes=%s title=%s", len(data), title[:60])
        return data


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

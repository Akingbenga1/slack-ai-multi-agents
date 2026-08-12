"""PdfRenderer + fpdf2 adapter smoke (Sprint 37.3)."""

from __future__ import annotations

import ast
from pathlib import Path

from api.app.pdf_renderer import Fpdf2PdfRenderer
from api.app.slack.pdf_export import analysis_to_pdf_bytes


def test_fpdf2_adapter_renders_pdf_bytes():
    data = Fpdf2PdfRenderer().render(
        title="Competitor analysis",
        body="Acme grew 12%.\n\nBeta lagged.",
        subtitle="Source: q3.csv",
    )
    assert data.startswith(b"%PDF")
    assert len(data) > 100


def test_analysis_to_pdf_bytes_facade():
    data = analysis_to_pdf_bytes(title="T", body="Hello")
    assert data.startswith(b"%PDF")


def test_pdf_export_facade_does_not_import_fpdf():
    """Product facade module must not import fpdf by name."""
    path = Path("api/app/slack/pdf_export.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("fpdf"), alias.name
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("fpdf"), node.module

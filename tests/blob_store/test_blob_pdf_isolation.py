"""Blob store + PDF renderer product isolation (Sprint 37.4)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from api.app.settings import Settings
from api.app.uploads.roles import FileRole
from api.app.uploads.storage import store_upload

_REPO = Path(__file__).resolve().parents[2]
_APP = _REPO / "api" / "app"

# Product blob I/O must not own filesystem put/get/rename.
_FORBIDDEN_FS_IO = re.compile(r"\b(write_bytes|read_bytes|Path\.rename)\b")

_BLOB_PRODUCT = (
    _APP / "uploads" / "storage.py",
    _APP / "slack" / "files" / "intake.py",
    _APP / "slack" / "files" / "rename.py",
    _APP / "workflows" / "library.py",
    _APP / "ingest" / "upload_ingest.py",
)

_PDF_PRODUCT = (
    _APP / "slack" / "pdf_export.py",
    _APP / "slack" / "files" / "pdf.py",
    _APP / "slack" / "delivery" / "strategies.py",
)


def _ast_imports_fpdf(path: Path) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "fpdf" or alias.name.startswith("fpdf."):
                    return alias.name
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "fpdf" or node.module.startswith("fpdf."):
                return node.module
    return None


def test_pdf_product_does_not_import_fpdf_sdk():
    for path in _PDF_PRODUCT:
        hit = _ast_imports_fpdf(path)
        assert hit is None, f"{path.name} imports {hit!r}"


def test_pdf_export_facade_has_no_fpdf2_adapter_name():
    tree = ast.parse((_APP / "slack" / "pdf_export.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in {
            "fpdf",
            "FPDF",
            "Fpdf2PdfRenderer",
        }:
            pytest.fail(f"pdf_export names {node.id!r}")
        if isinstance(node, ast.Attribute) and node.attr == "FPDF":
            pytest.fail("pdf_export references FPDF")


def test_pdf_export_uses_pdf_renderer_strategy():
    text = (_APP / "slack" / "pdf_export.py").read_text(encoding="utf-8")
    assert "PdfRenderer" in text
    assert "default_pdf_renderer" in text
    assert "r.render(" in text


def test_blob_product_uses_blob_store():
    for path in _BLOB_PRODUCT:
        text = path.read_text(encoding="utf-8")
        assert (
            "BlobStore" in text
            or "resolve_blob_store" in text
            or "get_blob_store" in text
        ), f"{path.name} does not reference BlobStore"


def test_blob_product_has_no_direct_filesystem_blob_io():
    """Adapters own write_bytes / read_bytes / Path.rename for blobs."""
    for path in _BLOB_PRODUCT:
        text = path.read_text(encoding="utf-8")
        hit = _FORBIDDEN_FS_IO.search(text)
        assert hit is None, f"{path.name} owns filesystem I/O {hit.group(0)!r}"


def test_demo_default_blob_store_is_local():
    assert Settings().blob_store == "local"


def test_store_upload_fail_closed_missing_client_id(tmp_path: Path):
    with pytest.raises(ValueError, match="client_id is required"):
        store_upload(
            upload_root=tmp_path,
            client_id="",
            file_role=FileRole.DOCUMENT,
            filename="x.csv",
            data=b"a,b\n",
        )
    with pytest.raises(ValueError, match="client_id is required"):
        store_upload(
            upload_root=tmp_path,
            client_id="   ",
            file_role=FileRole.DOCUMENT,
            filename="x.csv",
            data=b"a,b\n",
        )

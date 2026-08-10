"""Tests for document chunking + upload ingest routing (Task 8.3)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from api.app.ingest.document_chunk import chunk_document_unit
from api.app.ingest.document_pipeline import point_id_for_document_chunk
from api.app.ingest.documents.schema import (
    DocumentFormat,
    DocumentUnit,
    DocumentUnitKind,
)
from api.app.ingest.upload_ingest import ingest_upload
from api.app.settings import Settings
from api.app.uploads.roles import FileRole
from api.app.uploads.storage import store_upload


def _unit(**kwargs) -> DocumentUnit:
    base = {
        "text": "Acme onboarding checklist step one",
        "unit_index": 0,
        "source_format": DocumentFormat.PDF,
        "kind": DocumentUnitKind.PAGE,
        "locator": "page=1",
        "filename": "guide.pdf",
    }
    base.update(kwargs)
    return DocumentUnit(**base)


def test_document_chunk_and_point_id_idempotent():
    chunks = chunk_document_unit(_unit())
    assert len(chunks) == 1
    assert "kind=document" in chunks[0].text
    assert "locator=page=1" in chunks[0].text
    a = point_id_for_document_chunk("tenant-a", chunks[0])
    b = point_id_for_document_chunk("tenant-a", chunks[0])
    c = point_id_for_document_chunk("tenant-b", chunks[0])
    assert a == b
    assert a != c


def test_ingest_upload_document_calls_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = Settings(upload_dir=str(tmp_path / "uploads"))
    stored = store_upload(
        upload_root=settings.upload_dir_path,
        client_id="11111111-1111-1111-1111-111111111111",
        file_role=FileRole.DOCUMENT,
        filename="catalog.csv",
        data=b"product,price\nWidget,9\n",
    )

    fake_result = MagicMock(
        unit_count=1,
        chunk_count=1,
        point_ids=["p1"],
    )
    monkeypatch.setattr(
        "api.app.ingest.upload_ingest.ingest_extracted_document",
        lambda **_kwargs: fake_result,
    )

    result = ingest_upload(
        client_id=stored.client_id,
        file_role=FileRole.DOCUMENT,
        relative_path=stored.relative_path,
        filename=stored.original_filename,
        settings=settings,
    )
    assert result.chunk_count == 1
    assert result.file_role is FileRole.DOCUMENT
    assert result.point_ids == ["p1"]


def test_ingest_upload_slack_history_calls_messages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    settings = Settings(upload_dir=str(tmp_path / "uploads"))
    csv = b"channel,ts,user,text\nC1,1.1,U1,hello\n"
    stored = store_upload(
        upload_root=settings.upload_dir_path,
        client_id="11111111-1111-1111-1111-111111111111",
        file_role=FileRole.SLACK_HISTORY,
        filename="hist.csv",
        data=csv,
    )

    fake = MagicMock(message_count=1, chunk_count=1, point_ids=["m1"])
    monkeypatch.setattr(
        "api.app.ingest.upload_ingest.ingest_messages",
        lambda **_kwargs: fake,
    )

    result = ingest_upload(
        client_id=stored.client_id,
        file_role=FileRole.SLACK_HISTORY,
        relative_path=stored.relative_path,
        filename=stored.original_filename,
        settings=settings,
    )
    assert result.unit_or_message_count == 1
    assert result.point_ids == ["m1"]

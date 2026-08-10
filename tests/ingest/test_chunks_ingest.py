"""Unit tests for shared ingest_chunks core (Task 29.1)."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from api.app.ingest.chunks_ingest import DEFAULT_EMBED_BATCH, ingest_chunks
from api.app.ingest.document_pipeline import (
    document_chunk_payload,
    point_id_for_document_chunk,
)
from api.app.ingest.document_chunk import chunk_document_unit
from api.app.ingest.documents.schema import (
    DocumentFormat,
    DocumentUnit,
    DocumentUnitKind,
)
from api.app.ingest.pipeline import chunk_payload, point_id_for_chunk
from api.app.ingest.chunk import chunk_message
from api.app.ingest.schema import NormalizedMessage, SourceFormat
from api.app.settings import Settings


@dataclass
class _FakeChunk:
    text: str


def test_default_embed_batch_constant():
    assert DEFAULT_EMBED_BATCH == 32


def test_ingest_chunks_empty_skips_tei(monkeypatch: pytest.MonkeyPatch):
    tei = MagicMock()
    upsert = MagicMock()
    monkeypatch.setattr(
        "api.app.ingest.chunks_ingest.upsert_vectors",
        upsert,
    )
    ids = ingest_chunks(
        client_id="t1",
        chunks=[],
        point_id_fn=lambda _c, ch: ch.text,
        payload_fn=lambda ch: {"text": ch.text},
        tei=tei,
        settings=Settings(),
    )
    assert ids == []
    tei.embed.assert_not_called()
    upsert.assert_not_called()


def test_ingest_chunks_batches_and_strategies(monkeypatch: pytest.MonkeyPatch):
    settings = Settings()
    tei = MagicMock()
    tei.embed.side_effect = lambda texts: [[float(i)] * 3 for i, _ in enumerate(texts)]
    upsert_calls: list[dict] = []

    def fake_upsert(**kwargs):
        upsert_calls.append(kwargs)

    monkeypatch.setattr(
        "api.app.ingest.chunks_ingest.upsert_vectors",
        fake_upsert,
    )

    chunks = [_FakeChunk(text=f"c{i}") for i in range(5)]
    ids = ingest_chunks(
        client_id="tenant-x",
        chunks=chunks,
        point_id_fn=lambda client_id, ch: f"{client_id}:{ch.text}",
        payload_fn=lambda ch: {"kind": "fake", "text": ch.text},
        tei=tei,
        settings=settings,
        embed_batch_size=2,
    )

    assert ids == [f"tenant-x:c{i}" for i in range(5)]
    assert tei.embed.call_count == 3  # 2 + 2 + 1
    assert len(upsert_calls) == 3
    assert upsert_calls[0]["ids"] == ["tenant-x:c0", "tenant-x:c1"]
    assert upsert_calls[0]["payloads"][0]["kind"] == "fake"
    assert upsert_calls[2]["ids"] == ["tenant-x:c4"]


def test_slack_and_document_strategies_still_distinct():
    msg = NormalizedMessage(
        channel="C1",
        ts="1.1",
        user="U1",
        text="hello",
        source_format=SourceFormat.JSON,
    )
    slack_chunk = chunk_message(msg)[0]
    unit = DocumentUnit(
        text="hello",
        unit_index=0,
        source_format=DocumentFormat.PDF,
        kind=DocumentUnitKind.PAGE,
        locator="page=1",
        filename="a.pdf",
    )
    doc_chunk = chunk_document_unit(unit)[0]

    sid = point_id_for_chunk("t", slack_chunk)
    did = point_id_for_document_chunk("t", doc_chunk)
    assert sid != did
    assert chunk_payload(slack_chunk)["kind"] == "slack_message"
    assert document_chunk_payload(doc_chunk)["kind"] == "document"

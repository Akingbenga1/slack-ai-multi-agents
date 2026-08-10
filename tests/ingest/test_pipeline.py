"""Unit tests for chunking + deterministic point ids (Task 7.5)."""

from api.app.ingest.chunk import chunk_message, chunk_messages, content_hash
from api.app.ingest.pipeline import point_id_for_chunk
from api.app.ingest.schema import NormalizedMessage, SourceFormat


def _msg(**kwargs) -> NormalizedMessage:
    base = {
        "channel": "C1",
        "ts": "1.1",
        "user": "U1",
        "text": "hello world",
        "source_format": SourceFormat.JSON,
    }
    base.update(kwargs)
    return NormalizedMessage(**base)


def test_chunk_short_message_single():
    chunks = chunk_message(_msg())
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].chunk_count == 1
    assert "channel=C1" in chunks[0].text
    assert "hello world" in chunks[0].text
    assert chunks[0].content_hash == content_hash(chunks[0].text)


def test_chunk_long_message_splits():
    body = "x" * 3500
    chunks = chunk_message(_msg(text=body), max_chars=1000, overlap=50)
    assert len(chunks) >= 3
    assert all(c.chunk_count == len(chunks) for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_point_id_idempotent():
    chunks = chunk_messages([_msg()])
    a = point_id_for_chunk("tenant-a", chunks[0])
    b = point_id_for_chunk("tenant-a", chunks[0])
    c = point_id_for_chunk("tenant-b", chunks[0])
    assert a == b
    assert a != c
    # UUID string form
    assert len(a) == 36

"""Unit tests for live Slack history sync (Task 9.3)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from api.app.ingest import SourceFormat
from api.app.ingest.pipeline import IngestResult
from api.app.slack.sync import sync_slack_history
from api.app.slack.watermarks import SOURCE_SLACK_LIVE, bounds_from_watermark


class FakeSlackClient:
    def __init__(self, channels: list[dict], history: dict[str, list[dict]]):
        self._channels = channels
        self._history = history
        self.history_calls: list[dict[str, Any]] = []

    def conversations_list(self, **_kwargs: Any):
        return iter(self._channels)

    def conversations_history(self, channel: str, **kwargs: Any):
        self.history_calls.append({"channel": channel, **kwargs})
        return iter(self._history.get(channel, []))


class FakeDB:
    """Minimal session for watermark get/upsert used by sync."""

    def __init__(self):
        self.rows: dict[tuple, Any] = {}

    def scalar(self, _stmt):
        # sync only calls get_watermark via select — we key by last touch
        # Prefer returning the only matching channel if one exists.
        if len(self.rows) == 1:
            return next(iter(self.rows.values()))
        return None

    def add(self, row):
        self.rows[(row.tenant_id, row.source, row.channel_id)] = row

    def commit(self):
        return None

    def refresh(self, row):
        return row


def test_sync_incremental_ingests_web_api_and_advances_watermark(monkeypatch):
    tenant_id = uuid4()
    db = FakeDB()
    client = FakeSlackClient(
        channels=[{"id": "C1"}],
        history={
            "C1": [
                {"type": "message", "user": "U1", "text": "hello", "ts": "200.0"},
                {"type": "message", "user": "U2", "text": "world", "ts": "210.0"},
                {"type": "message", "subtype": "channel_join", "text": "joined", "ts": "211.0"},
            ]
        },
    )

    # Seed prior watermark so history is called with oldest=latest
    from api.app.db.models import SyncWatermark

    prior = SyncWatermark(
        tenant_id=tenant_id,
        source=SOURCE_SLACK_LIVE,
        channel_id="C1",
        cursor="100.0",
        meta={"oldest": "50.0", "latest": "100.0"},
    )
    db.add(prior)

    def fake_get(_db, *, tenant_id, channel_id, source=SOURCE_SLACK_LIVE):
        return db.rows.get((tenant_id, source, channel_id))

    monkeypatch.setattr("api.app.slack.sync.get_watermark", fake_get)
    monkeypatch.setattr("api.app.slack.watermarks.get_watermark", fake_get)

    ingested: list[Any] = []

    def fake_ingest(*, client_id, messages, settings=None, **_kwargs):
        msgs = list(messages)
        ingested.extend(msgs)
        return IngestResult(client_id=client_id, message_count=len(msgs), chunk_count=len(msgs))

    result = sync_slack_history(
        db,
        tenant_id=tenant_id,
        client=client,
        ingest_fn=fake_ingest,
        settings=object(),  # unused by fake ingest
    )

    assert client.history_calls[0]["channel"] == "C1"
    assert client.history_calls[0]["oldest"] == "100.0"
    assert result.message_count == 2
    assert result.chunk_count == 2
    assert all(m.source_format is SourceFormat.WEB_API for m in ingested)
    assert [m.text for m in ingested] == ["hello", "world"]

    row = db.rows[(tenant_id, SOURCE_SLACK_LIVE, "C1")]
    oldest, latest = bounds_from_watermark(row)
    assert oldest == "50.0"  # prior oldest kept (min)
    assert latest == "210.0"
    assert row.cursor == "210.0"


def test_sync_empty_channel_skips_ingest(monkeypatch):
    tenant_id = uuid4()
    db = FakeDB()
    client = FakeSlackClient(channels=[{"id": "C2"}], history={"C2": []})

    monkeypatch.setattr(
        "api.app.slack.sync.get_watermark",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "api.app.slack.watermarks.get_watermark",
        lambda *_a, **_k: None,
    )

    calls = {"n": 0}

    def fake_ingest(**_kwargs):
        calls["n"] += 1
        return IngestResult(client_id=str(tenant_id), message_count=0, chunk_count=0)

    result = sync_slack_history(
        db,
        tenant_id=tenant_id,
        channel_ids=["C2"],
        client=client,
        ingest_fn=fake_ingest,
        settings=object(),
    )
    assert calls["n"] == 0
    assert result.channels[0].skipped is True
    assert (tenant_id, SOURCE_SLACK_LIVE, "C2") in db.rows


def test_sync_ingests_in_batches(monkeypatch):
    from api.app.settings import Settings

    tenant_id = uuid4()
    db = FakeDB()
    history = {
        "C1": [
            {"type": "message", "user": "U1", "text": f"m{i}", "ts": f"{100 + i}.0"}
            for i in range(5)
        ]
    }
    client = FakeSlackClient(channels=[{"id": "C1"}], history=history)
    monkeypatch.setattr(
        "api.app.slack.sync.get_watermark",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "api.app.slack.watermarks.get_watermark",
        lambda *_a, **_k: None,
    )

    ingest_sizes: list[int] = []

    def fake_ingest(*, client_id, messages, settings=None, **_kwargs):
        msgs = list(messages)
        ingest_sizes.append(len(msgs))
        # Watermark must not advance until the full channel pull finishes.
        assert (tenant_id, SOURCE_SLACK_LIVE, "C1") not in db.rows
        return IngestResult(
            client_id=client_id, message_count=len(msgs), chunk_count=len(msgs)
        )

    settings = Settings(slack_sync_ingest_batch_size=2)
    result = sync_slack_history(
        db,
        tenant_id=tenant_id,
        channel_ids=["C1"],
        client=client,
        ingest_fn=fake_ingest,
        settings=settings,
    )
    assert result.message_count == 5
    assert ingest_sizes == [2, 2, 1]
    row = db.rows[(tenant_id, SOURCE_SLACK_LIVE, "C1")]
    _, latest = bounds_from_watermark(row)
    assert latest == "104.0"


def test_download_rejects_non_slack_host():
    from api.app.slack.client import SlackApiError, SlackWebClient

    client = SlackWebClient("xoxb-test", sleep=lambda _: None)
    with pytest.raises(SlackApiError, match="download_host_not_allowed"):
        client.download_file("https://evil.example/steal")
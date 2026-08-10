"""Unit tests for Slack sync watermarks (Task 9.2)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from api.app.slack import watermarks as wm


def test_ts_min_max():
    assert wm.ts_min("100.0", "99.5") == "99.5"
    assert wm.ts_max("100.0", "99.5") == "100.0"
    assert wm.ts_min(None, "1.0") == "1.0"
    assert wm.ts_max("1.0", None) == "1.0"
    assert wm.ts_min(None, None) is None


def test_bounds_from_watermark_prefers_meta_then_cursor():
    row = SimpleNamespace(meta={"oldest": "10.0", "latest": "20.0"}, cursor="20.0")
    assert wm.bounds_from_watermark(row) == ("10.0", "20.0")

    row2 = SimpleNamespace(meta=None, cursor="15.0")
    assert wm.bounds_from_watermark(row2) == (None, "15.0")

    assert wm.bounds_from_watermark(None) == (None, None)


def test_upsert_creates_and_merges(monkeypatch: pytest.MonkeyPatch):
    tenant_id = uuid4()
    store: dict[tuple, object] = {}
    commits: list[int] = []

    class FakeDB:
        def add(self, row):
            store[(row.tenant_id, row.source, row.channel_id)] = row

        def commit(self):
            commits.append(1)

        def refresh(self, row):
            return row

    def fake_get(_db, *, tenant_id, channel_id, source=wm.SOURCE_SLACK_LIVE):
        return store.get((tenant_id, source, channel_id))

    monkeypatch.setattr(wm, "get_watermark", fake_get)
    db = FakeDB()

    created = wm.upsert_watermark(
        db,
        tenant_id=tenant_id,
        channel_id="C1",
        oldest="100.0",
        latest="110.0",
        last_synced_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert created.cursor == "110.0"
    assert created.meta == {"oldest": "100.0", "latest": "110.0"}

    updated = wm.upsert_watermark(
        db,
        tenant_id=tenant_id,
        channel_id="C1",
        oldest="90.0",  # earlier bootstrap bound
        latest="120.0",  # advance high-water
        last_synced_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    assert updated.meta["oldest"] == "90.0"
    assert updated.meta["latest"] == "120.0"
    assert updated.cursor == "120.0"
    assert len(commits) == 2
    assert updated is created


def test_upsert_requires_channel():
    with pytest.raises(ValueError, match="channel_id"):
        wm.upsert_watermark(SimpleNamespace(), tenant_id=uuid4(), channel_id="")

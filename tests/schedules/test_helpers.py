"""Shared ScheduleStore + kind Strategy smoke (Task 28.4)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from api.app.schedules.kinds import (
    RECURRING_REPORT_KEY,
    SLACK_HISTORY_SYNC_KEY,
    get_schedule_kind,
    list_due_for_kind,
)
from api.app.schedules.store import get_block, upsert_block
from tests.schedules.helpers import FakeScheduleDB, report_block, sync_block


def test_store_upsert_and_get_block():
    tenant_id = uuid4()
    db = FakeScheduleDB()
    upsert_block(
        db,
        tenant_id=tenant_id,
        key=SLACK_HISTORY_SYNC_KEY,
        block=sync_block(enabled=False),
    )
    assert get_block(db, tenant_id, SLACK_HISTORY_SYNC_KEY) == {"enabled": False}


def test_strategy_normalize_defaults():
    sync = get_schedule_kind(SLACK_HISTORY_SYNC_KEY)
    report = get_schedule_kind(RECURRING_REPORT_KEY)
    assert sync.normalize(None) == {"enabled": True}
    assert report.normalize(None)["enabled"] is False
    assert report.normalize(None)["cadence"] == "weekly"


def test_list_due_for_kind_uses_seeded_blocks(monkeypatch: pytest.MonkeyPatch):
    t_on, t_off = uuid4(), uuid4()
    db = FakeScheduleDB(install_tenant_ids=[t_on, t_off])
    db.seed(t_on, {SLACK_HISTORY_SYNC_KEY: sync_block(enabled=True)})
    db.seed(t_off, {SLACK_HISTORY_SYNC_KEY: sync_block(enabled=False)})
    monkeypatch.setattr(
        "api.app.schedules.kinds.tenant_has_entitlement",
        lambda *_a, **_k: True,
    )
    assert list_due_for_kind(db, SLACK_HISTORY_SYNC_KEY) == [t_on]


def test_report_block_factory_window():
    daily = report_block(enabled=True, channel_id="C1", cadence="daily")
    assert daily["window_label"] == "last 24 hours"
    weekly = report_block(cadence="weekly")
    assert weekly["window_label"] == "last 7 days"

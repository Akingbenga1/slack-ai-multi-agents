"""Unit tests for recurring report schedule (Task 17.2 / 28.x)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from api.app.reports import schedule as sched
from tests.schedules.helpers import FakeScheduleDB, report_block


def test_defaults_disabled_without_config():
    out = sched.get_recurring_report_schedule(FakeScheduleDB(), uuid4())
    assert out["enabled"] is False
    assert out["cadence"] == "weekly"
    assert out["channel_id"] is None
    assert out["window_label"] == "last 7 days"


def test_get_respects_stored_fields():
    tenant_id = uuid4()
    db = FakeScheduleDB()
    db.seed(
        tenant_id,
        {
            sched.SCHEDULE_KEY: report_block(
                enabled=True,
                channel_id="C123",
                cadence="daily",
                window_label="last 24 hours",
            )
        },
    )
    out = sched.get_recurring_report_schedule(db, tenant_id)
    assert out["enabled"] is True
    assert out["channel_id"] == "C123"
    assert out["cadence"] == "daily"
    assert out["window_label"] == "last 24 hours"


def test_set_creates_and_updates():
    tenant_id = uuid4()
    db = FakeScheduleDB()
    created = sched.set_recurring_report_schedule(
        db,
        tenant_id=tenant_id,
        enabled=True,
        channel_id="C_REPORT",
        cadence="daily",
    )
    block = created.schedules[sched.SCHEDULE_KEY]
    assert block["enabled"] is True
    assert block["channel_id"] == "C_REPORT"
    assert block["cadence"] == "daily"
    assert block["window_label"] == "last 24 hours"

    updated = sched.set_recurring_report_schedule(
        db,
        tenant_id=tenant_id,
        cadence="weekly",
        clear_channel=True,
    )
    assert updated is created
    block = updated.schedules[sched.SCHEDULE_KEY]
    assert block["channel_id"] is None
    assert block["cadence"] == "weekly"
    assert block["window_label"] == "last 7 days"


def test_normalize_cadence_rejects_bad():
    with pytest.raises(ValueError):
        sched.normalize_cadence("hourly")


def test_list_tenants_requires_enabled_channel(monkeypatch: pytest.MonkeyPatch):
    t_ok, t_no_chan, t_off = uuid4(), uuid4(), uuid4()
    db = FakeScheduleDB(install_tenant_ids=[t_ok, t_no_chan, t_off])
    db.seed(
        t_ok,
        {
            sched.SCHEDULE_KEY: report_block(
                enabled=True, channel_id="C1", cadence="weekly"
            )
        },
    )
    db.seed(
        t_no_chan,
        {sched.SCHEDULE_KEY: report_block(enabled=True, channel_id=None)},
    )
    db.seed(
        t_off,
        {
            sched.SCHEDULE_KEY: report_block(
                enabled=False, channel_id="C2", cadence="daily"
            )
        },
    )
    monkeypatch.setattr(
        "api.app.schedules.kinds.tenants_with_entitlement",
        lambda _db, ids, _flag: set(ids),
    )
    due = sched.list_tenants_for_scheduled_reports(db)
    assert len(due) == 1
    assert due[0]["tenant_id"] == t_ok
    assert due[0]["channel_id"] == "C1"

    daily = sched.list_tenants_for_scheduled_reports(db, cadence="daily")
    assert daily == []


def test_list_tenants_skips_unentitled(monkeypatch: pytest.MonkeyPatch):
    t_ok = uuid4()
    db = FakeScheduleDB(install_tenant_ids=[t_ok])
    db.seed(
        t_ok,
        {
            sched.SCHEDULE_KEY: report_block(
                enabled=True, channel_id="C1", cadence="weekly"
            )
        },
    )
    monkeypatch.setattr(
        "api.app.schedules.kinds.tenants_with_entitlement",
        lambda *_a, **_k: set(),
    )
    assert sched.list_tenants_for_scheduled_reports(db) == []


def test_list_tenants_skips_already_posted_period(monkeypatch: pytest.MonkeyPatch):
    from datetime import datetime, timezone

    from api.app.schedules.kinds import period_key_for_cadence

    t_ok = uuid4()
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    period = period_key_for_cadence("weekly", when=now)
    db = FakeScheduleDB(install_tenant_ids=[t_ok])
    block = report_block(enabled=True, channel_id="C1", cadence="weekly")
    block["last_posted_period"] = period
    db.seed(t_ok, {sched.SCHEDULE_KEY: block})
    monkeypatch.setattr(
        "api.app.schedules.kinds.tenants_with_entitlement",
        lambda _db, ids, _flag: set(ids),
    )
    from api.app.schedules.kinds import list_due_recurring_reports

    assert list_due_recurring_reports(db, now=now) == []
    # Next week still due
    later = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
    due = list_due_recurring_reports(db, now=later)
    assert len(due) == 1
    assert due[0]["tenant_id"] == t_ok

"""Unit tests for recurring report schedule (Task 17.2)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from api.app.db.models import AgentConfig
from api.app.reports import schedule as sched


def test_defaults_disabled_without_config():
    class FakeDB:
        def scalar(self, _stmt):
            return None

    out = sched.get_recurring_report_schedule(FakeDB(), uuid4())
    assert out["enabled"] is False
    assert out["cadence"] == "weekly"
    assert out["channel_id"] is None
    assert out["window_label"] == "last 7 days"


def test_get_respects_stored_fields():
    tenant_id = uuid4()
    config = AgentConfig(
        tenant_id=tenant_id,
        name=sched.DEFAULT_AGENT_NAME,
        schedules={
            sched.SCHEDULE_KEY: {
                "enabled": True,
                "channel_id": "C123",
                "cadence": "daily",
                "window_label": "last 24 hours",
            }
        },
    )

    class FakeDB:
        def scalar(self, _stmt):
            return config

    out = sched.get_recurring_report_schedule(FakeDB(), tenant_id)
    assert out["enabled"] is True
    assert out["channel_id"] == "C123"
    assert out["cadence"] == "daily"
    assert out["window_label"] == "last 24 hours"


def test_set_creates_and_updates():
    tenant_id = uuid4()
    store: dict[str, AgentConfig] = {}

    class FakeDB:
        def scalar(self, _stmt):
            return store.get("cfg")

        def add(self, row):
            store["cfg"] = row

        def commit(self):
            return None

        def refresh(self, row):
            return row

    db = FakeDB()
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

    class FakeDB:
        def scalars(self, _stmt):
            return SimpleNamespace(all=lambda: [t_ok, t_no_chan, t_off])

    def fake_get(_db, tenant_id):
        if tenant_id == t_ok:
            return {
                "enabled": True,
                "channel_id": "C1",
                "cadence": "weekly",
                "window_label": "last 7 days",
            }
        if tenant_id == t_no_chan:
            return {
                "enabled": True,
                "channel_id": None,
                "cadence": "weekly",
                "window_label": "last 7 days",
            }
        return {
            "enabled": False,
            "channel_id": "C2",
            "cadence": "daily",
            "window_label": "last 24 hours",
        }

    monkeypatch.setattr(sched, "get_recurring_report_schedule", fake_get)
    monkeypatch.setattr(sched, "tenant_has_entitlement", lambda *_a, **_k: True)
    due = sched.list_tenants_for_scheduled_reports(FakeDB())
    assert len(due) == 1
    assert due[0]["tenant_id"] == t_ok
    assert due[0]["channel_id"] == "C1"

    daily = sched.list_tenants_for_scheduled_reports(FakeDB(), cadence="daily")
    assert daily == []


def test_list_tenants_skips_unentitled(monkeypatch: pytest.MonkeyPatch):
    t_ok = uuid4()

    class FakeDB:
        def scalars(self, _stmt):
            return SimpleNamespace(all=lambda: [t_ok])

    monkeypatch.setattr(
        sched,
        "get_recurring_report_schedule",
        lambda *_a, **_k: {
            "enabled": True,
            "channel_id": "C1",
            "cadence": "weekly",
            "window_label": "last 7 days",
        },
    )
    monkeypatch.setattr(sched, "tenant_has_entitlement", lambda *_a, **_k: False)
    assert sched.list_tenants_for_scheduled_reports(FakeDB()) == []

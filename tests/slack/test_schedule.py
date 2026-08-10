"""Unit tests for Slack history sync schedule + Beat due list (Task 9.4)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from api.app.db.models import AgentConfig
from api.app.slack import schedule as sched


def test_enabled_defaults_true_without_config():
    class FakeDB:
        def scalar(self, _stmt):
            return None

    assert sched.is_slack_history_sync_enabled(FakeDB(), uuid4()) is True


def test_enabled_respects_explicit_false():
    tenant_id = uuid4()
    config = AgentConfig(
        tenant_id=tenant_id,
        name=sched.DEFAULT_AGENT_NAME,
        schedules={sched.SCHEDULE_KEY: {"enabled": False}},
    )

    class FakeDB:
        def scalar(self, _stmt):
            return config

    assert sched.is_slack_history_sync_enabled(FakeDB(), tenant_id) is False


def test_set_enabled_creates_and_updates():
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
    created = sched.set_slack_history_sync_enabled(db, tenant_id=tenant_id, enabled=False)
    assert created.schedules[sched.SCHEDULE_KEY]["enabled"] is False
    assert sched.is_slack_history_sync_enabled(db, tenant_id) is False

    updated = sched.set_slack_history_sync_enabled(db, tenant_id=tenant_id, enabled=True)
    assert updated is created
    assert updated.schedules[sched.SCHEDULE_KEY]["enabled"] is True


def test_list_tenants_filters_disabled(monkeypatch: pytest.MonkeyPatch):
    t_on, t_off = uuid4(), uuid4()

    class FakeDB:
        def scalars(self, _stmt):
            return SimpleNamespace(all=lambda: [t_on, t_off])

    monkeypatch.setattr(
        sched,
        "is_slack_history_sync_enabled",
        lambda _db, tenant_id: tenant_id == t_on,
    )
    monkeypatch.setattr(
        sched,
        "tenant_has_entitlement",
        lambda _db, tenant_id, _flag: True,
    )
    assert sched.list_tenants_for_scheduled_slack_sync(FakeDB()) == [t_on]


def test_list_tenants_skips_unentitled(monkeypatch: pytest.MonkeyPatch):
    t_ok, t_no = uuid4(), uuid4()

    class FakeDB:
        def scalars(self, _stmt):
            return SimpleNamespace(all=lambda: [t_ok, t_no])

    monkeypatch.setattr(sched, "is_slack_history_sync_enabled", lambda *_a, **_k: True)
    monkeypatch.setattr(
        sched,
        "tenant_has_entitlement",
        lambda _db, tenant_id, _flag: tenant_id == t_ok,
    )
    assert sched.list_tenants_for_scheduled_slack_sync(FakeDB()) == [t_ok]

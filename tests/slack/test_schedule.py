"""Unit tests for Slack history sync schedule + Beat due list (Task 9.4 / 28.x)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from api.app.slack import schedule as sched
from tests.schedules.helpers import FakeScheduleDB, sync_block


def test_enabled_defaults_true_without_config():
    assert sched.is_slack_history_sync_enabled(FakeScheduleDB(), uuid4()) is True


def test_enabled_respects_explicit_false():
    tenant_id = uuid4()
    db = FakeScheduleDB()
    db.seed(tenant_id, {sched.SCHEDULE_KEY: sync_block(enabled=False)})
    assert sched.is_slack_history_sync_enabled(db, tenant_id) is False


def test_set_enabled_creates_and_updates():
    tenant_id = uuid4()
    db = FakeScheduleDB()
    created = sched.set_slack_history_sync_enabled(db, tenant_id=tenant_id, enabled=False)
    assert created.schedules[sched.SCHEDULE_KEY]["enabled"] is False
    assert sched.is_slack_history_sync_enabled(db, tenant_id) is False

    updated = sched.set_slack_history_sync_enabled(db, tenant_id=tenant_id, enabled=True)
    assert updated is created
    assert updated.schedules[sched.SCHEDULE_KEY]["enabled"] is True


def test_list_tenants_filters_disabled(monkeypatch: pytest.MonkeyPatch):
    t_on, t_off = uuid4(), uuid4()
    db = FakeScheduleDB(install_tenant_ids=[t_on, t_off])
    db.seed(t_on, {sched.SCHEDULE_KEY: sync_block(enabled=True)})
    db.seed(t_off, {sched.SCHEDULE_KEY: sync_block(enabled=False)})
    monkeypatch.setattr(
        "api.app.schedules.kinds.tenant_has_entitlement",
        lambda *_a, **_k: True,
    )
    assert sched.list_tenants_for_scheduled_slack_sync(db) == [t_on]


def test_list_tenants_skips_unentitled(monkeypatch: pytest.MonkeyPatch):
    t_ok, t_no = uuid4(), uuid4()
    db = FakeScheduleDB(install_tenant_ids=[t_ok, t_no])
    db.seed(t_ok, {sched.SCHEDULE_KEY: sync_block(enabled=True)})
    db.seed(t_no, {sched.SCHEDULE_KEY: sync_block(enabled=True)})
    monkeypatch.setattr(
        "api.app.schedules.kinds.tenant_has_entitlement",
        lambda _db, tenant_id, _flag: tenant_id == t_ok,
    )
    assert sched.list_tenants_for_scheduled_slack_sync(db) == [t_ok]

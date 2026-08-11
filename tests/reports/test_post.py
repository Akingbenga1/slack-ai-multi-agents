"""Tests for recurring report post path (Task 17.3)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from api.app.reports import post as post_mod


class _FakeInstall:
    bot_token_encrypted = "enc"


def test_post_recurring_report_direct_channel(monkeypatch: pytest.MonkeyPatch):
    tenant_id = uuid4()
    posts: list[dict] = []

    monkeypatch.setattr(
        post_mod,
        "get_recurring_report_schedule",
        lambda _db, _tid: {
            "enabled": True,
            "channel_id": "C_REPORT",
            "cadence": "weekly",
            "window_label": "last 7 days",
        },
    )
    monkeypatch.setattr(
        post_mod,
        "claim_recurring_report_period",
        lambda *_a, **_k: (
            True,
            "2026-W33",
            {
                "enabled": True,
                "channel_id": "C_REPORT",
                "cadence": "weekly",
                "window_label": "last 7 days",
            },
        ),
    )
    monkeypatch.setattr(
        post_mod,
        "release_recurring_report_period_claim",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        post_mod,
        "mark_recurring_report_posted",
        lambda *_a, **_k: {"period": "2026-W33", "last_posted_at": "x"},
    )
    monkeypatch.setattr(
        post_mod,
        "get_install_by_tenant",
        lambda _db, _tid: _FakeInstall(),
    )
    monkeypatch.setattr(post_mod, "get_bot_token", lambda *_a, **_k: "xoxb-test")

    def fake_sync(*_a, **_k):
        return SimpleNamespace(as_dict=lambda: {"message_count": 2})

    monkeypatch.setattr(post_mod, "sync_slack_history", fake_sync)

    def fake_run_report(**kwargs):
        assert kwargs["channel"] == "C_REPORT"
        assert kwargs["window_label"] == "last 7 days"
        return {
            "answer": "# Recurring report\n\n- Theme one",
            "retrieved_chunks": [
                {"label": "slack C_REPORT ts=1", "kind": "slack_message"}
            ],
            "hedge": False,
            "usage_tokens": 12,
        }

    def fake_post(**kwargs):
        posts.append(kwargs)
        return {"ok": True, "ts": "999.1"}

    out = post_mod.post_recurring_report(
        object(),  # db unused (helpers patched)
        tenant_id=tenant_id,
        run_report_fn=fake_run_report,
        post_message_fn=fake_post,
        sync_fn=fake_sync,
        record_usage=False,
    )
    assert out["channel_id"] == "C_REPORT"
    assert out["slack_ts"] == "999.1"
    assert out["sync"]["ok"] is True
    assert len(posts) == 1
    assert posts[0]["channel"] == "C_REPORT"
    assert posts[0]["thread_ts"] is None  # direct channel post
    assert "Theme one" in posts[0]["text"] or "theme" in posts[0]["text"].lower()


def test_post_continues_when_sync_fails(monkeypatch: pytest.MonkeyPatch):
    tenant_id = uuid4()

    monkeypatch.setattr(
        post_mod,
        "get_recurring_report_schedule",
        lambda *_a, **_k: {
            "enabled": True,
            "channel_id": "C1",
            "cadence": "daily",
            "window_label": "last 24 hours",
        },
    )
    monkeypatch.setattr(
        post_mod,
        "claim_recurring_report_period",
        lambda *_a, **_k: (
            True,
            "2026-08-10",
            {
                "enabled": True,
                "channel_id": "C1",
                "cadence": "daily",
                "window_label": "last 24 hours",
            },
        ),
    )
    monkeypatch.setattr(
        post_mod,
        "release_recurring_report_period_claim",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        post_mod,
        "mark_recurring_report_posted",
        lambda *_a, **_k: {"period": "2026-08-10", "last_posted_at": "x"},
    )
    monkeypatch.setattr(
        post_mod, "get_install_by_tenant", lambda *_a, **_k: _FakeInstall()
    )
    monkeypatch.setattr(post_mod, "get_bot_token", lambda *_a, **_k: "xoxb-test")

    def boom(*_a, **_k):
        raise RuntimeError("sync down")

    out = post_mod.post_recurring_report(
        object(),
        tenant_id=tenant_id,
        prefer_sync=True,
        sync_fn=boom,
        run_report_fn=lambda **_k: {
            "answer": "ok",
            "retrieved_chunks": [],
            "hedge": True,
            "usage_tokens": 0,
        },
        post_message_fn=lambda **_k: {"ok": True, "ts": "1.0"},
        record_usage=False,
    )
    assert out["sync"]["attempted"] is True
    assert out["sync"]["ok"] is False
    assert out["sync"]["stale"] is True
    assert out["slack_ts"] == "1.0"


def test_post_requires_channel(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        post_mod,
        "get_recurring_report_schedule",
        lambda *_a, **_k: {
            "enabled": True,
            "channel_id": None,
            "cadence": "weekly",
            "window_label": "last 7 days",
        },
    )
    with pytest.raises(ValueError, match="channel_id"):
        post_mod.post_recurring_report(object(), tenant_id=uuid4())


def test_dispatch_enqueues_due_tenants(monkeypatch: pytest.MonkeyPatch):
    from worker import tasks as worker_tasks

    from tests.schedules.helpers import FakeScheduleDB

    t1 = uuid4()
    enqueued: list[dict] = []

    from worker import tenant_job as tenant_job_mod

    monkeypatch.setattr(tenant_job_mod, "session_scope", lambda: FakeScheduleDB())
    monkeypatch.setattr(
        worker_tasks,
        "list_due_recurring_reports",
        lambda _db, cadence=None: [
            {
                "tenant_id": t1,
                "channel_id": "C9",
                "cadence": "weekly",
                "window_label": "last 7 days",
            }
        ],
    )

    class _R:
        def __init__(self, tid: str):
            self.id = f"task-{tid[:8]}"

    def fake_enqueue(**kwargs):
        enqueued.append(kwargs)
        return _R(kwargs["client_id"])

    monkeypatch.setattr(worker_tasks, "enqueue_recurring_report", fake_enqueue)
    result = worker_tasks.dispatch_recurring_reports.run(cadence="weekly")
    assert result["count"] == 1
    assert enqueued[0]["channel_id"] == "C9"
    assert enqueued[0]["prefer_sync"] is True

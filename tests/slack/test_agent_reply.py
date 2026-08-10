"""Slack → LangGraph reply path (Sprint 14.1 / 14.3)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.billing.plans import ACTIVE_ENTITLEMENTS, apply_plan_state
from api.app.db.models import BillingCustomer, Tenant, UsageEvent
from api.app.governance.usage import EVENT_LLM_TOKENS, record_usage
from api.app.settings import Settings
from api.app.slack.agent_reply import (
    MSG_PLAN_INACTIVE,
    check_agent_entitlement,
    process_agent_reply,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):  # noqa: ANN001
    return "TEXT"


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Tenant.__table__.create(engine)
    BillingCustomer.__table__.create(engine)
    UsageEvent.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _tenant_with_plan(db: Session, *, active: bool = True) -> Tenant:
    t = Tenant(id=uuid4(), slug=f"org-{uuid4().hex[:8]}", name="Org", status="active")
    db.add(t)
    db.flush()
    row = BillingCustomer(
        tenant_id=t.id,
        stripe_customer_id=f"cus_{uuid4().hex[:8]}",
        plan_status="inactive",
        entitlements={},
    )
    db.add(row)
    db.flush()
    if active:
        apply_plan_state(db, row, plan_status="active", stripe_subscription_id="sub_x")
    db.commit()
    return t


def test_inactive_plan_denied(db: Session):
    t = _tenant_with_plan(db, active=False)
    ok, msg = check_agent_entitlement(db, t.id)
    assert ok is False
    assert msg == MSG_PLAN_INACTIVE


def test_active_plan_allowed(db: Session):
    t = _tenant_with_plan(db, active=True)
    ok, msg = check_agent_entitlement(db, t.id)
    assert ok is True
    assert msg == ""


def test_over_token_budget_denied(db: Session):
    t = _tenant_with_plan(db, active=True)
    row = db.query(BillingCustomer).filter_by(tenant_id=t.id).one()
    row.entitlements = {**dict(ACTIVE_ENTITLEMENTS), "tokens_daily": 10}
    db.add(row)
    db.commit()
    now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
    record_usage(db, t.id, EVENT_LLM_TOKENS, units=10, commit=True)
    # Force created_at into the same UTC day window as `now`
    for ev in db.query(UsageEvent).filter_by(tenant_id=t.id).all():
        ev.created_at = now
    db.commit()

    ok, msg = check_agent_entitlement(db, t.id, now=now)
    assert ok is False
    assert "budget" in msg.lower()
    assert "10" in msg


class _NoCloseSession:
    """Wrap a Session so process_agent_reply's finally close is a no-op."""

    def __init__(self, inner: Session):
        self._inner = inner

    def __getattr__(self, name: str):
        return getattr(self._inner, name)

    def close(self) -> None:
        return None


def test_process_agent_reply_posts_grounded_answer(db: Session):
    t = _tenant_with_plan(db, active=True)
    posts: list[dict] = []

    def fake_post(**kwargs):
        posts.append(kwargs)
        return {"ok": True}

    def fake_run_agent(**kwargs):
        assert kwargs["client_id"] == str(t.id)
        assert kwargs["question"] == "refund policy"
        return {
            "answer": "Refunds within 30 days.",
            "retrieved_chunks": [
                {"label": "document refund.csv", "kind": "document"},
            ],
            "hedge": False,
            "workflow": "qa",
            "usage_tokens": 12,
        }

    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    result = process_agent_reply(
        tenant_id=t.id,
        bot_token="xoxb-test",
        event={
            "type": "app_mention",
            "channel": "C1",
            "ts": "100.1",
            "text": "<@UBOT> refund policy",
        },
        team_id="T1",
        settings=settings,
        db_factory=lambda: _NoCloseSession(db),
        run_agent_fn=fake_run_agent,
        post_fn=fake_post,
    )
    assert result["ok"] is True
    assert result["denied"] is False
    assert len(posts) == 1
    assert "Refunds within 30 days." in posts[0]["text"]
    assert "*Sources:*" in posts[0]["text"]
    assert posts[0]["thread_ts"] == "100.1"


def test_process_agent_reply_denies_inactive(db: Session):
    t = _tenant_with_plan(db, active=False)
    posts: list[dict] = []
    called = {"agent": False}

    def fake_run_agent(**_kwargs):
        called["agent"] = True
        return {}

    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    result = process_agent_reply(
        tenant_id=t.id,
        bot_token="xoxb-test",
        event={
            "type": "message",
            "channel_type": "im",
            "channel": "D1",
            "text": "hello",
        },
        settings=settings,
        db_factory=lambda: _NoCloseSession(db),
        run_agent_fn=fake_run_agent,
        post_fn=lambda **kw: posts.append(kw) or {"ok": True},
    )
    assert result["denied"] is True
    assert called["agent"] is False
    assert posts[0]["text"] == MSG_PLAN_INACTIVE
    assert posts[0].get("thread_ts") is None

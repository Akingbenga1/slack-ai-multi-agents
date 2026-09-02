"""Tests for shared Slack event dispatch (HTTP + Socket Mode)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.billing.plans import apply_plan_state
from api.app.db.models import BillingCustomer, SlackInstall, Tenant
from api.app.settings import Settings
from api.app.slack.event_dispatch import (
    dispatch_events_api_payload,
    enqueue_agent_reply_for_event,
    resolve_team_id,
    should_process_slack_event,
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
    for table in (Tenant.__table__, BillingCustomer.__table__, SlackInstall.__table__):
        table.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_install(db: Session, *, team_id: str = "TWORK123") -> Tenant:
    tenant = Tenant(
        id=uuid4(),
        slug=f"org-{uuid4().hex[:8]}",
        name="Org",
        status="active",
    )
    db.add(tenant)
    db.flush()
    billing = BillingCustomer(
        tenant_id=tenant.id,
        external_customer_id=f"cus_{uuid4().hex[:8]}",
        plan_status="inactive",
        entitlements={},
    )
    db.add(billing)
    db.flush()
    apply_plan_state(db, billing, plan_status="active", external_subscription_id="sub_x")
    install = SlackInstall(
        tenant_id=tenant.id,
        team_id=team_id,
        team_name="Workspace",
        bot_token_encrypted="enc",
        scopes="chat:write",
    )
    db.add(install)
    db.commit()
    return tenant


def test_resolve_team_id_from_payload():
    payload = {"team_id": "T123", "event": {"type": "app_mention"}}
    assert resolve_team_id(payload, payload["event"]) == "T123"


def test_should_process_app_mention(db: Session):
    tenant = _seed_install(db)
    event = {
        "type": "app_mention",
        "channel": "C1",
        "text": "<@U1> hello",
    }
    allowed, reason, tenant_id = should_process_slack_event(
        event=event,
        team_id="TWORK123",
        db=db,
        settings=Settings(),
    )
    assert allowed is True
    assert reason is None
    assert tenant_id == tenant.id


def test_should_skip_bot_message(db: Session):
    _seed_install(db)
    event = {"type": "message", "bot_id": "B1", "channel": "D1"}
    allowed, reason, _ = should_process_slack_event(
        event=event,
        team_id="TWORK123",
        db=db,
        settings=Settings(),
    )
    assert allowed is False
    assert reason == "not_replyable"


@patch("api.app.slack.event_dispatch.get_bot_token", return_value="xoxb-test")
@patch("api.app.slack.event_dispatch.process_agent_reply")
def test_enqueue_uses_background_callback(
    mock_reply: MagicMock,
    _mock_token: MagicMock,
    db: Session,
):
    _seed_install(db)
    background = MagicMock()
    event = {"type": "app_mention", "channel": "C1", "text": "hi"}
    result = enqueue_agent_reply_for_event(
        event=event,
        team_id="TWORK123",
        settings=Settings(),
        db=db,
        background=background,
    )
    assert result["queued"] is True
    background.assert_called_once()
    mock_reply.assert_not_called()


@patch("api.app.slack.event_dispatch.get_bot_token", return_value="xoxb-test")
@patch("api.app.slack.event_dispatch.process_agent_reply")
def test_dispatch_event_callback(
    mock_reply: MagicMock,
    _mock_token: MagicMock,
    db: Session,
):
    _seed_install(db)
    payload = {
        "type": "event_callback",
        "team_id": "TWORK123",
        "event": {
            "type": "app_mention",
            "channel": "C1",
            "text": "<@U1> summarize",
        },
    }
    background = MagicMock()
    result = dispatch_events_api_payload(
        payload,
        settings=Settings(),
        db=db,
        background=background,
    )
    assert result["queued"] is True
    background.assert_called_once()
    mock_reply.assert_not_called()

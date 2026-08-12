"""Stripe webhook plan lifecycle tests (Task 11.4)."""

from __future__ import annotations

from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.billing.webhooks import WebhookError, construct_stripe_event, handle_stripe_event
from api.app.db.models import BillingCustomer, Tenant
from api.app.settings import Settings


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
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _row(db: Session, *, customer_id: str = "cus_1") -> BillingCustomer:
    t = Tenant(id=uuid4(), slug=f"org-{uuid4().hex[:8]}", name="Org", status="active")
    db.add(t)
    db.flush()
    row = BillingCustomer(
        tenant_id=t.id,
        external_customer_id=customer_id,
        plan_status="inactive",
        meta={},
    )
    db.add(row)
    db.flush()
    return row


def test_construct_requires_secret():
    settings = Settings(stripe_webhook_secret="", stripe_secret_key="sk_test_x")
    with pytest.raises(WebhookError, match="STRIPE_WEBHOOK_SECRET"):
        construct_stripe_event(b"{}", "t=1,v1=x", settings)


def test_construct_requires_signature():
    settings = Settings(stripe_webhook_secret="whsec_x", stripe_secret_key="sk_test_x")
    with pytest.raises(WebhookError, match="Missing Stripe-Signature"):
        construct_stripe_event(b"{}", "", settings)


def test_checkout_completed_activates(db: Session):
    row = _row(db)
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "mode": "subscription",
                "client_reference_id": str(row.tenant_id),
                "customer": "cus_1",
                "subscription": "sub_1",
                "metadata": {"tenant_id": str(row.tenant_id)},
            }
        },
    }
    result = handle_stripe_event(db, event)
    assert result["handled"] is True
    db.refresh(row)
    assert row.plan_status == "active"
    assert row.external_subscription_id == "sub_1"
    assert row.entitlements.get("agent") is True
    assert row.entitlements.get("ingest") is True
    assert row.entitlements.get("sync") is True


def test_subscription_updated_deactivates_when_canceled(db: Session):
    row = _row(db)
    row.plan_status = "active"
    row.external_subscription_id = "sub_1"
    db.flush()
    event = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_1",
                "customer": "cus_1",
                "status": "canceled",
                "metadata": {"tenant_id": str(row.tenant_id)},
            }
        },
    }
    result = handle_stripe_event(db, event)
    assert result["handled"] is True
    db.refresh(row)
    assert row.plan_status == "inactive"


def test_subscription_deleted_clears_subscription(db: Session):
    row = _row(db)
    row.plan_status = "active"
    row.external_subscription_id = "sub_1"
    db.flush()
    event = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_1",
                "customer": "cus_1",
                "status": "canceled",
                "metadata": {},
            }
        },
    }
    result = handle_stripe_event(db, event)
    assert result["handled"] is True
    db.refresh(row)
    assert row.plan_status == "inactive"
    assert row.external_subscription_id is None
    assert row.entitlements.get("agent") is False


def test_unknown_event_ignored(db: Session):
    result = handle_stripe_event(db, {"type": "invoice.paid", "data": {"object": {}}})
    assert result["handled"] is False


def test_webhook_skips_admin_locked_plan(db: Session):
    row = _row(db)
    row.plan_status = "active"
    row.plan_source = "admin"
    row.override_reason = "operator waiver"
    row.external_subscription_id = "sub_1"
    db.flush()
    event = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_1",
                "customer": "cus_1",
                "status": "canceled",
                "metadata": {},
            }
        },
    }
    result = handle_stripe_event(db, event)
    assert result["handled"] is False
    assert result["reason"] == "admin_plan_lock"
    db.refresh(row)
    assert row.plan_status == "active"
    assert row.plan_source == "admin"
    assert row.external_subscription_id == "sub_1"


def test_construct_event_delegates_to_stripe(monkeypatch: pytest.MonkeyPatch):
    settings = Settings(stripe_webhook_secret="whsec_x", stripe_secret_key="sk_test_x")
    fake_event = MagicMock(type="checkout.session.completed")
    mock = MagicMock(return_value=fake_event)
    monkeypatch.setattr("stripe.Webhook.construct_event", mock)
    out = construct_stripe_event(b'{"id":"evt_1"}', "t=1,v1=abc", settings)
    assert out is fake_event
    mock.assert_called_once()

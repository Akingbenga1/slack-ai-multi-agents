"""First-org hardening (Sprint 22.1) — seed readiness + entitlement gates."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.billing.plans import (
    ACTIVE_ENTITLEMENTS,
    apply_plan_state,
    require_entitlement,
    tenant_has_entitlement,
)
from api.app.db.models import AgentConfig, BillingCustomer, Membership, Tenant, User
from api.app.demo.readiness import demo_readiness
from api.app.governance.budgets import check_budget
from api.app.membership import DEMO_ADMIN_ID, DEMO_OWNER_ID, DEMO_TENANT_ID
from api.app.reports import schedule as report_sched
from api.app.slack import schedule as sync_sched
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


def test_require_entitlement_denies_inactive(db: Session):
    t = Tenant(id=uuid4(), slug="x", name="X", status="active")
    db.add(t)
    db.flush()
    row = BillingCustomer(
        tenant_id=t.id,
        plan_status="inactive",
        entitlements={},
    )
    db.add(row)
    db.commit()
    with pytest.raises(HTTPException) as ei:
        require_entitlement(db, t.id, "sync")
    assert ei.value.status_code == 403
    assert ei.value.detail["flag"] == "sync"


def test_require_entitlement_allows_active(db: Session):
    t = Tenant(id=uuid4(), slug="y", name="Y", status="active")
    db.add(t)
    db.flush()
    row = BillingCustomer(tenant_id=t.id, plan_status="inactive", entitlements={})
    db.add(row)
    db.flush()
    apply_plan_state(db, row, plan_status="active", stripe_subscription_id="sub_t")
    db.commit()
    require_entitlement(db, t.id, "ingest")
    assert tenant_has_entitlement(db, t.id, "ingest") is True


def test_inactive_budget_require_active_plan(db: Session):
    t = Tenant(id=uuid4(), slug="z", name="Z", status="active")
    db.add(t)
    db.flush()
    db.add(BillingCustomer(tenant_id=t.id, plan_status="inactive", entitlements={}))
    db.commit()
    d = check_budget(db, t.id, "jobs", units=1, require_active_plan=True)
    assert d.allowed is False
    assert d.reason == "plan_inactive"


def test_demo_readiness_checks():
    role_id = uuid4()
    tenant = Tenant(
        id=DEMO_TENANT_ID,
        slug="demo-org",
        name="Demo Organisation",
        status="active",
    )
    owner = User(
        id=DEMO_OWNER_ID,
        email="owner@example.com",
        display_name="Platform Owner",
        hashed_password="x",
        is_active=True,
    )
    admin = User(
        id=DEMO_ADMIN_ID,
        email="admin@example.com",
        display_name="Org Admin",
        hashed_password="x",
        is_active=True,
    )
    membership = Membership(
        id=uuid4(),
        tenant_id=DEMO_TENANT_ID,
        user_id=DEMO_ADMIN_ID,
        role_id=role_id,
    )
    agent = AgentConfig(
        id=uuid4(),
        tenant_id=DEMO_TENANT_ID,
        name="default",
        schedules={"slack_history_sync": {"enabled": True}},
    )
    billing = BillingCustomer(
        id=uuid4(),
        tenant_id=DEMO_TENANT_ID,
        plan_status="active",
        entitlements=dict(ACTIVE_ENTITLEMENTS),
    )

    class FakeDB:
        def get(self, model, key):
            if model is Tenant and key == DEMO_TENANT_ID:
                return tenant
            if model is User and key == DEMO_OWNER_ID:
                return owner
            if model is User and key == DEMO_ADMIN_ID:
                return admin
            return None

        def scalar(self, stmt):
            text = str(stmt)
            if "billing_customers" in text:
                return billing
            if "memberships" in text:
                return membership
            if "agent_configs" in text:
                return agent
            if "slack_installs" in text:
                return None
            return None

    payload = demo_readiness(FakeDB())
    assert payload["tenant_id"] == str(DEMO_TENANT_ID)
    assert payload["checks"]["tenant_exists"]
    assert payload["checks"]["owner_user"]
    assert payload["checks"]["admin_user"]
    assert payload["checks"]["admin_membership"]
    assert payload["checks"]["billing_row"]
    assert payload["checks"]["plan_active"]
    assert payload["checks"]["entitlement_agent"]
    assert payload["ready_for_paid_demo"] is True


def test_demo_activate_plan_setting_parsed():
    assert Settings(demo_activate_plan=True).demo_activate_plan is True
    assert Settings(demo_activate_plan=False).demo_activate_plan is False
    assert Settings(demo_report_channel_id="C123").demo_report_channel_id == "C123"


def test_beat_lists_respect_entitlements(monkeypatch: pytest.MonkeyPatch):
    from types import SimpleNamespace

    t = uuid4()

    class FakeDB:
        def scalars(self, _stmt):
            return SimpleNamespace(all=lambda: [t])

    monkeypatch.setattr(sync_sched, "is_slack_history_sync_enabled", lambda *_a, **_k: True)
    monkeypatch.setattr(sync_sched, "tenant_has_entitlement", lambda *_a, **_k: False)
    assert sync_sched.list_tenants_for_scheduled_slack_sync(FakeDB()) == []

    monkeypatch.setattr(
        report_sched,
        "get_recurring_report_schedule",
        lambda *_a, **_k: {
            "enabled": True,
            "channel_id": "C1",
            "cadence": "weekly",
            "window_label": "last 7 days",
        },
    )
    monkeypatch.setattr(report_sched, "tenant_has_entitlement", lambda *_a, **_k: False)
    assert report_sched.list_tenants_for_scheduled_reports(FakeDB()) == []

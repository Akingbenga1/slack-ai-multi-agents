"""Budget checks (Task 12.2)."""

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
from api.app.governance.budgets import check_budget
from api.app.governance.usage import EVENT_JOB, EVENT_LLM_TOKENS, record_usage


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


def _active_tenant(db: Session) -> Tenant:
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
    apply_plan_state(db, row, plan_status="active", stripe_subscription_id="sub_x")
    db.commit()
    return t


def test_active_plan_grants_default_budgets(db: Session):
    t = _active_tenant(db)
    row = db.query(BillingCustomer).filter_by(tenant_id=t.id).one()
    assert row.entitlements["jobs_daily"] == ACTIVE_ENTITLEMENTS["jobs_daily"]
    assert row.entitlements["tokens_daily"] == ACTIVE_ENTITLEMENTS["tokens_daily"]


def test_jobs_budget_allows_then_blocks(db: Session):
    t = _active_tenant(db)
    row = db.query(BillingCustomer).filter_by(tenant_id=t.id).one()
    row.entitlements = {**dict(row.entitlements), "jobs_daily": 2}
    db.add(row)
    db.commit()

    now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
    assert check_budget(db, t.id, "jobs", units=1, now=now).allowed is True
    record_usage(db, t.id, EVENT_JOB, units=1, commit=True)
    record_usage(db, t.id, EVENT_JOB, units=1, commit=True)
    blocked = check_budget(db, t.id, "jobs", units=1, now=now)
    assert blocked.allowed is False
    assert blocked.reason == "budget_exceeded"
    assert blocked.used == 2
    assert blocked.limit == 2


def test_tokens_daily_and_monthly(db: Session):
    t = _active_tenant(db)
    row = db.query(BillingCustomer).filter_by(tenant_id=t.id).one()
    row.entitlements = {
        **dict(row.entitlements),
        "tokens_daily": 100,
        "tokens_monthly": 10_000,
    }
    db.add(row)
    db.commit()

    now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
    record_usage(db, t.id, EVENT_LLM_TOKENS, units=90, commit=True)
    ok = check_budget(db, t.id, "tokens", units=5, now=now)
    assert ok.allowed is True
    blocked = check_budget(db, t.id, "tokens", units=20, now=now)
    assert blocked.allowed is False
    assert blocked.window == "daily"


def test_inactive_plan_skips_by_default(db: Session):
    t = Tenant(id=uuid4(), slug="inactive-org", name="I", status="active")
    db.add(t)
    db.flush()
    db.add(
        BillingCustomer(
            tenant_id=t.id,
            plan_status="inactive",
            entitlements={"jobs_daily": 0, "agent": False},
        )
    )
    db.commit()
    d = check_budget(db, t.id, "jobs", units=1)
    assert d.allowed is True
    assert d.reason == "plan_inactive"
    d2 = check_budget(db, t.id, "jobs", units=1, require_active_plan=True)
    assert d2.allowed is False
    assert d2.reason == "plan_inactive"

"""Usage summary aggregates + API (Task 12.4)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.auth.tokens import create_access_token
from api.app.billing.plans import ACTIVE_ENTITLEMENTS, apply_plan_state
from api.app.db.models import BillingCustomer, Tenant, UsageEvent
from api.app.db.session import get_db
from api.app.governance.summary import build_usage_summary
from api.app.governance.usage import (
    EVENT_JOB,
    EVENT_LLM_TOKENS,
    EVENT_SLACK_MENTION,
    record_usage,
)
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID, DEMO_TENANT_ID
from api.app.settings import Settings, get_settings


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
    t = Tenant(id=uuid4(), slug=f"s-{uuid4().hex[:8]}", name="S", status="active")
    db.add(t)
    db.flush()
    row = BillingCustomer(
        tenant_id=t.id,
        external_customer_id=f"cus_{uuid4().hex[:8]}",
        plan_status="inactive",
        entitlements={},
    )
    db.add(row)
    db.flush()
    apply_plan_state(db, row, plan_status="active", external_subscription_id="sub_x")
    db.commit()
    return t


def _record(db: Session, tenant_id, event_type: str, *, units: int, when: datetime):
    row = record_usage(db, tenant_id, event_type, units=units, commit=False)
    row.created_at = when
    return row


def test_build_usage_summary_aggregates_and_budgets(db: Session):
    t = _active_tenant(db)
    now = datetime(2026, 8, 8, 15, 0, tzinfo=timezone.utc)
    _record(db, t.id, EVENT_SLACK_MENTION, units=1, when=now)
    _record(db, t.id, EVENT_SLACK_MENTION, units=1, when=now)
    _record(db, t.id, EVENT_JOB, units=1, when=now)
    _record(db, t.id, EVENT_LLM_TOKENS, units=500, when=now)

    other = Tenant(id=uuid4(), slug=f"o-{uuid4().hex[:8]}", name="O", status="active")
    db.add(other)
    db.flush()
    _record(db, other.id, EVENT_JOB, units=99, when=now)
    db.commit()

    summary = build_usage_summary(db, t.id, window="day", now=now)
    assert summary["tenant_id"] == str(t.id)
    assert summary["window"] == "day"
    assert summary["plan_active"] is True
    assert summary["totals"]["event_count"] == 4
    assert summary["totals"]["units"] == 503

    by = {r["event_type"]: r for r in summary["by_event_type"]}
    assert by[EVENT_SLACK_MENTION]["event_count"] == 2
    assert by[EVENT_LLM_TOKENS]["units"] == 500
    assert by[EVENT_JOB]["event_count"] == 1

    budgets = {b["key"]: b for b in summary["budgets"]}
    assert budgets["tokens_daily"]["used"] == 500
    assert budgets["tokens_daily"]["limit"] == ACTIVE_ENTITLEMENTS["tokens_daily"]
    assert budgets["jobs_daily"]["used"] == 1
    assert budgets["jobs_daily"]["remaining"] == ACTIVE_ENTITLEMENTS["jobs_daily"] - 1


def test_summary_empty_inactive_plan(db: Session):
    t = Tenant(id=uuid4(), slug=f"i-{uuid4().hex[:8]}", name="I", status="active")
    db.add(t)
    db.commit()
    now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
    summary = build_usage_summary(db, t.id, window="month", now=now)
    assert summary["totals"] == {"event_count": 0, "units": 0}
    assert summary["by_event_type"] == []
    assert summary["plan_active"] is False
    for b in summary["budgets"]:
        assert b["limit"] == 0
        assert b["used"] == 0


@pytest.fixture
def client(db: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")

    def _override_db():
        yield db

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _token(tenant_id: str | None = None) -> str:
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    return create_access_token(
        settings=settings,
        sub=str(DEMO_ADMIN_ID),
        email="admin@example.com",
        role="org_admin",
        tenant_id=tenant_id or str(DEMO_TENANT_ID),
    )


def test_usage_summary_requires_auth(client: TestClient):
    assert client.get("/usage/summary").status_code == 401


def test_usage_summary_ok(client: TestClient, db: Session):
    tid = uuid4()
    t = Tenant(id=tid, slug=f"demo-{tid.hex[:8]}", name="Demo", status="active")
    db.add(t)
    db.flush()
    row = BillingCustomer(
        tenant_id=t.id,
        external_customer_id="cus_demo",
        plan_status="inactive",
        entitlements={},
    )
    db.add(row)
    db.flush()
    apply_plan_state(db, row, plan_status="active", external_subscription_id="sub_demo")
    _record(db, t.id, EVENT_SLACK_MENTION, units=1, when=datetime.now(timezone.utc))
    db.commit()

    res = client.get(
        "/usage/summary?window=day",
        headers={"Authorization": f"Bearer {_token(str(t.id))}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["tenant_id"] == str(t.id)
    assert body["totals"]["event_count"] >= 1
    assert any(r["event_type"] == EVENT_SLACK_MENTION for r in body["by_event_type"])
    assert "budgets" in body


def test_usage_summary_cross_tenant_denied(client: TestClient):
    other = str(uuid4())
    res = client.get(
        "/usage/summary",
        headers={
            "Authorization": f"Bearer {_token(str(DEMO_TENANT_ID))}",
            "X-Client-Id": other,
        },
    )
    assert res.status_code == 403

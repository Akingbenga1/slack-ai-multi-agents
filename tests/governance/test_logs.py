"""Usage event + job log APIs (Task 20.2)."""

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
from api.app.db.models import Job, Tenant, UsageEvent
from api.app.db.session import get_db
from api.app.governance.logs import list_jobs, list_usage_events
from api.app.governance.usage import EVENT_LLM_TOKENS, EVENT_SLACK_MENTION, record_usage
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
    UsageEvent.__table__.create(engine)
    Job.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db: Session):
    def _override_db():
        try:
            yield db
        finally:
            pass

    def _settings():
        return Settings(jwt_secret="test-secret-at-least-32-chars-long!")

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_settings] = _settings
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


def _tenant(db: Session) -> Tenant:
    t = Tenant(id=uuid4(), slug=f"l-{uuid4().hex[:8]}", name="Logs", status="active")
    db.add(t)
    db.flush()
    return t


def test_list_usage_events_filters(db: Session):
    t = _tenant(db)
    record_usage(db, t.id, EVENT_SLACK_MENTION, units=1, commit=False)
    record_usage(db, t.id, EVENT_LLM_TOKENS, units=10, commit=False)
    db.commit()
    all_rows, all_total = list_usage_events(db, t.id, limit=10)
    assert all_total == 2
    assert len(all_rows) == 2
    mentions, mention_total = list_usage_events(db, t.id, event_type=EVENT_SLACK_MENTION)
    assert mention_total == 1
    assert len(mentions) == 1
    assert mentions[0].event_type == EVENT_SLACK_MENTION


def test_list_jobs_failed_only(db: Session):
    t = _tenant(db)
    db.add(
        Job(
            tenant_id=t.id,
            kind="slack_history_sync",
            status="succeeded",
        )
    )
    db.add(
        Job(
            tenant_id=t.id,
            kind="slack_history_sync",
            status="failed",
            error="boom",
        )
    )
    db.commit()
    failed, total = list_jobs(db, t.id, status="failed")
    assert total == 1
    assert len(failed) == 1
    assert failed[0].error == "boom"


def test_usage_events_api_ok(client: TestClient, db: Session):
    t = _tenant(db)
    record_usage(db, t.id, EVENT_SLACK_MENTION, units=1, commit=True)
    res = client.get(
        "/usage/events?event_type=slack_mention",
        headers={"Authorization": f"Bearer {_token(str(t.id))}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["tenant_id"] == str(t.id)
    assert body["total"] == 1
    assert len(body["events"]) == 1
    assert body["events"][0]["event_type"] == EVENT_SLACK_MENTION


def test_usage_jobs_api_ok(client: TestClient, db: Session):
    t = _tenant(db)
    db.add(
        Job(
            tenant_id=t.id,
            kind="ingest",
            status="failed",
            error="parse failed",
            finished_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    res = client.get(
        "/usage/jobs?status=failed",
        headers={"Authorization": f"Bearer {_token(str(t.id))}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert len(body["jobs"]) == 1
    assert body["jobs"][0]["error"] == "parse failed"


def test_usage_events_cross_tenant_denied(client: TestClient):
    other = str(uuid4())
    res = client.get(
        "/usage/events",
        headers={
            "Authorization": f"Bearer {_token(str(DEMO_TENANT_ID))}",
            "X-Client-Id": other,
        },
    )
    assert res.status_code == 403

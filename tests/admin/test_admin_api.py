"""Platform admin tenant list/detail + support actions (Sprint 21)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.app.auth.tokens import create_access_token
from api.app.db.models import AuditLog, BillingCustomer, Tenant
from api.app.db.session import get_db
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID, DEMO_OWNER_ID, DEMO_TENANT_ID
from api.app.settings import Settings, get_settings


class _FakeDB:
    def __init__(self, tenants: list[Tenant] | None = None):
        self.tenants = tenants or []
        self.billing: dict = {}
        self.installs: dict = {}
        self.audit: list[AuditLog] = []
        self._committed = False

    def scalars(self, stmt):
        # Very small stub: list Tenant or AuditLog ordered queries
        from api.app.db.models import AuditLog as AL
        from api.app.db.models import Tenant as T

        class _Result:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        # Heuristic: if selecting tenants
        text = str(stmt)
        if "tenants" in text and "audit_logs" not in text:
            return _Result(self.tenants)
        if "audit_logs" in text:
            return _Result(list(reversed(self.audit)))
        return _Result([])

    def scalar(self, stmt):
        text = str(stmt)
        if "billing_customers" in text:
            for t in self.tenants:
                if t.id in self.billing:
                    return self.billing[t.id]
            return None
        if "slack_installs" in text:
            for t in self.tenants:
                if t.id in self.installs:
                    return self.installs[t.id]
            return None
        if "jobs" in text or "sync_watermarks" in text:
            return None
        return None

    def get(self, model, key):
        if model is Tenant:
            for t in self.tenants:
                if t.id == key:
                    return t
            return None
        if model is BillingCustomer:
            return self.billing.get(key)
        return None

    def add(self, obj):
        if isinstance(obj, AuditLog):
            if obj.id is None:
                obj.id = uuid4()
            if obj.created_at is None:
                obj.created_at = datetime.now(timezone.utc)
            self.audit.append(obj)
        if isinstance(obj, BillingCustomer):
            self.billing[obj.tenant_id] = obj
        if isinstance(obj, Tenant):
            if obj not in self.tenants:
                self.tenants.append(obj)

    def flush(self):
        pass

    def commit(self):
        self._committed = True

    def refresh(self, obj):
        pass

    def execute(self, stmt):
        class _R:
            def all(self_inner):
                return []

        return _R()


@pytest.fixture
def settings() -> Settings:
    return Settings(jwt_secret="test-secret-at-least-32-chars-long!")


def _owner_token(settings: Settings) -> str:
    return create_access_token(
        settings=settings,
        sub=str(DEMO_OWNER_ID),
        email="owner@example.com",
        role="platform_owner",
        tenant_id=None,
    )


def _admin_token(settings: Settings) -> str:
    return create_access_token(
        settings=settings,
        sub=str(DEMO_ADMIN_ID),
        email="admin@example.com",
        role="org_admin",
        tenant_id=str(DEMO_TENANT_ID),
    )


def test_admin_tenants_requires_owner(settings: Settings, monkeypatch: pytest.MonkeyPatch):
    db = _FakeDB()

    def _fake_db():
        yield db

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _fake_db
    try:
        with TestClient(app) as client:
            res = client.get(
                "/admin/tenants",
                headers={"Authorization": f"Bearer {_admin_token(settings)}"},
            )
            assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_admin_list_and_detail(settings: Settings, monkeypatch: pytest.MonkeyPatch):
    tenant = Tenant(
        id=DEMO_TENANT_ID,
        slug="demo-org",
        name="Demo Organisation",
        status="active",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db = _FakeDB([tenant])
    db.billing[tenant.id] = BillingCustomer(
        id=uuid4(),
        tenant_id=tenant.id,
        plan_status="active",
        entitlements={"agent": True, "tokens_daily": 1000, "jobs_daily": 10},
    )

    monkeypatch.setattr(
        "api.app.admin.tenants.get_slack_history_sync_status",
        lambda _db, tid: {
            "client_id": str(tid),
            "kind": "slack_history_sync",
            "enabled": True,
            "slack_connected": False,
            "last_success": None,
            "last_failure": None,
            "last_job": None,
            "watermarks": {"channel_count": 0, "last_synced_at": None},
        },
    )

    def _fake_db():
        yield db

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _fake_db
    try:
        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {_owner_token(settings)}"}
            res = client.get("/admin/tenants", headers=headers)
            assert res.status_code == 200
            body = res.json()
            assert body["count"] == 1
            assert body["tenants"][0]["plan_status"] == "active"
            assert body["tenants"][0]["slack_connected"] is False

            detail = client.get(f"/admin/tenants/{DEMO_TENANT_ID}", headers=headers)
            assert detail.status_code == 200
            assert detail.json()["slug"] == "demo-org"
            assert "sync" in detail.json()
    finally:
        app.dependency_overrides.clear()


def test_admin_suspend_and_budget_override(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    tenant = Tenant(
        id=DEMO_TENANT_ID,
        slug="demo-org",
        name="Demo Organisation",
        status="active",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db = _FakeDB([tenant])
    db.billing[tenant.id] = BillingCustomer(
        id=uuid4(),
        tenant_id=tenant.id,
        plan_status="active",
        entitlements={"agent": True, "tokens_daily": 100, "jobs_daily": 5},
        meta={},
    )

    monkeypatch.setattr(
        "api.app.admin.actions.ensure_billing_customer",
        lambda _db, tenant_id, **_kw: db.billing[DEMO_TENANT_ID],
    )

    def _fake_db():
        yield db

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _fake_db
    try:
        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {_owner_token(settings)}"}
            res = client.patch(
                f"/admin/tenants/{DEMO_TENANT_ID}/status",
                headers=headers,
                json={"status": "suspended"},
            )
            assert res.status_code == 200
            assert res.json()["status"] == "suspended"
            assert tenant.status == "suspended"
            assert any(a.action == "tenant.status.set" for a in db.audit)

            res2 = client.patch(
                f"/admin/tenants/{DEMO_TENANT_ID}/budgets",
                headers=headers,
                json={"tokens_daily": 9999, "jobs_daily": 42},
            )
            assert res2.status_code == 200
            ents = res2.json()["entitlements"]
            assert ents["tokens_daily"] == 9999
            assert ents["jobs_daily"] == 42
            assert any(a.action == "tenant.budget.override" for a in db.audit)

            logs = client.get(
                f"/admin/audit-logs?tenant_id={DEMO_TENANT_ID}",
                headers=headers,
            )
            assert logs.status_code == 200
            assert logs.json()["count"] >= 2
    finally:
        app.dependency_overrides.clear()


def test_admin_plan_override(settings: Settings, monkeypatch: pytest.MonkeyPatch):
    tenant = Tenant(
        id=DEMO_TENANT_ID,
        slug="demo-org",
        name="Demo Organisation",
        status="active",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db = _FakeDB([tenant])
    db.billing[tenant.id] = BillingCustomer(
        id=uuid4(),
        tenant_id=tenant.id,
        plan_status="inactive",
        plan_source="stripe",
        entitlements={"agent": False},
        meta={},
    )

    monkeypatch.setattr(
        "api.app.admin.actions.ensure_billing_customer",
        lambda _db, tenant_id, **_kw: db.billing[DEMO_TENANT_ID],
    )

    def _fake_db():
        yield db

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _fake_db
    try:
        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {_owner_token(settings)}"}

            denied = client.patch(
                f"/admin/tenants/{DEMO_TENANT_ID}/plan",
                headers={"Authorization": f"Bearer {_admin_token(settings)}"},
                json={"plan_status": "active", "reason": "trial"},
            )
            assert denied.status_code == 403

            activate = client.patch(
                f"/admin/tenants/{DEMO_TENANT_ID}/plan",
                headers=headers,
                json={"plan_status": "active", "reason": "support trial"},
            )
            assert activate.status_code == 200
            body = activate.json()
            assert body["plan_status"] == "active"
            assert body["plan_source"] == "admin"
            assert body["override_reason"] == "support trial"
            assert body["entitlements"]["agent"] is True

            billing = db.billing[tenant.id]
            assert billing.plan_status == "active"
            assert billing.plan_source == "admin"
            assert any(a.action == "tenant.plan.override" for a in db.audit)

            deactivate = client.patch(
                f"/admin/tenants/{DEMO_TENANT_ID}/plan",
                headers=headers,
                json={"plan_status": "inactive", "reason": "trial ended"},
            )
            assert deactivate.status_code == 200
            body2 = deactivate.json()
            assert body2["plan_status"] == "inactive"
            assert body2["plan_source"] == "stripe"
            assert body2["override_reason"] is None
            assert body2["entitlements"]["agent"] is False
    finally:
        app.dependency_overrides.clear()


def test_admin_create_tenant(settings: Settings, monkeypatch: pytest.MonkeyPatch):
    tenant = Tenant(
        id=uuid4(),
        slug="acme-co",
        name="Acme Co",
        status="active",
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    db = _FakeDB([tenant])
    db.billing[tenant.id] = BillingCustomer(
        id=uuid4(),
        tenant_id=tenant.id,
        plan_status="inactive",
        entitlements={},
    )

    class _Created:
        def __init__(self):
            self.tenant = tenant
            self.admin = type(
                "U",
                (),
                {
                    "id": uuid4(),
                    "email": "acme@example.com",
                    "display_name": "Acme Admin",
                },
            )()
            self.created = True
            self.admin_password = "generated12"

    monkeypatch.setattr(
        "api.app.admin.routes.create_organisation",
        lambda *_a, **_k: _Created(),
    )
    monkeypatch.setattr(
        "api.app.admin.routes.tenant_summary_row",
        lambda _db, t: {
            "id": str(t.id),
            "slug": t.slug,
            "name": t.name,
            "status": t.status,
            "plan_status": "inactive",
            "slack_connected": False,
        },
    )

    def _fake_db():
        yield db

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _fake_db
    try:
        with TestClient(app) as client:
            denied = client.post(
                "/admin/tenants",
                headers={"Authorization": f"Bearer {_admin_token(settings)}"},
                json={
                    "name": "Acme Co",
                    "slug": "acme-co",
                    "admin_email": "acme@example.com",
                },
            )
            assert denied.status_code == 403

            res = client.post(
                "/admin/tenants",
                headers={"Authorization": f"Bearer {_owner_token(settings)}"},
                json={
                    "name": "Acme Co",
                    "slug": "acme-co",
                    "admin_email": "acme@example.com",
                },
            )
            assert res.status_code == 201
            body = res.json()
            assert body["tenant"]["slug"] == "acme-co"
            assert body["admin"]["email"] == "acme@example.com"
            assert body["admin_password"] == "generated12"
    finally:
        app.dependency_overrides.clear()


def test_admin_health_owner_only(settings: Settings, monkeypatch: pytest.MonkeyPatch):
    db = _FakeDB()

    monkeypatch.setattr(
        "api.app.admin.health_overview.run_deep_health",
        lambda _s: {
            "status": "ok",
            "checks": {
                "postgres": {"status": "ok"},
                "redis": {"status": "ok"},
                "vector_store": {"adapter": "qdrant", "status": "ok"},
                "embedding": {"adapter": "tei", "status": "ok"},
            },
        },
    )

    def _fake_db():
        yield db

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _fake_db
    try:
        with TestClient(app) as client:
            denied = client.get(
                "/admin/health",
                headers={"Authorization": f"Bearer {_admin_token(settings)}"},
            )
            assert denied.status_code == 403
            ok = client.get(
                "/admin/health",
                headers={"Authorization": f"Bearer {_owner_token(settings)}"},
            )
            assert ok.status_code == 200
            assert ok.json()["status"] == "ok"
            assert "errors" in ok.json()
    finally:
        app.dependency_overrides.clear()

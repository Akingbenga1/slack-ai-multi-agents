"""Upload storage + API tests (Task 8.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app.auth.tokens import create_access_token
from api.app.job_queue import EnqueueResult
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID, DEMO_OWNER_ID, DEMO_TENANT_ID
from api.app.settings import Settings, get_settings
from api.app.uploads.roles import FileRole
from api.app.uploads.storage import store_upload, validate_upload_filename


@pytest.fixture
def upload_root(tmp_path: Path) -> Path:
    root = tmp_path / "uploads"
    root.mkdir()
    return root


@pytest.fixture
def client(upload_root: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = Settings(
        upload_dir=str(upload_root),
        jwt_secret="test-secret-at-least-32-chars-long!",
    )
    monkeypatch.setattr("api.app.uploads.routes.get_settings", lambda: settings)

    class _FakeQueue:
        name = "celery"

        def enqueue(self, *, kind: str, tenant_id: str, payload=None):
            return EnqueueResult(task_id="task-test-1", queue="default", kind=kind)

    monkeypatch.setattr(
        "api.app.uploads.routes.get_job_queue",
        lambda: _FakeQueue(),
    )
    monkeypatch.setattr(
        "api.app.uploads.routes.require_entitlement",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "api.app.uploads.routes.require_budget",
        lambda *_a, **_k: None,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _token(*, role: str = "org_admin", tenant_id: str | None = None) -> str:
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    if role == "platform_owner":
        return create_access_token(
            settings=settings,
            sub=str(DEMO_OWNER_ID),
            email="owner@example.com",
            role="platform_owner",
            tenant_id=None,
        )
    return create_access_token(
        settings=settings,
        sub=str(DEMO_ADMIN_ID),
        email="admin@example.com",
        role="org_admin",
        tenant_id=tenant_id or str(DEMO_TENANT_ID),
    )


def test_validate_extensions():
    validate_upload_filename(FileRole.DOCUMENT, "guide.pdf")
    validate_upload_filename(FileRole.SLACK_HISTORY, "export.zip")
    with pytest.raises(ValueError):
        validate_upload_filename(FileRole.DOCUMENT, "export.zip")
    with pytest.raises(ValueError):
        validate_upload_filename(FileRole.SLACK_HISTORY, "guide.pdf")


def test_store_upload_writes_file(upload_root: Path):
    stored = store_upload(
        upload_root=upload_root,
        client_id=str(DEMO_TENANT_ID),
        file_role=FileRole.DOCUMENT,
        filename="notes.csv",
        data=b"a,b\n1,2\n",
        content_type="text/csv",
    )
    assert stored.absolute_path.is_file()
    assert stored.size_bytes == 8
    assert stored.relative_path.startswith(str(DEMO_TENANT_ID))


def test_upload_requires_auth(client: TestClient):
    res = client.post(
        "/uploads",
        data={"file_role": "document"},
        files={"file": ("a.csv", b"x,y\n1,2\n", "text/csv")},
    )
    assert res.status_code == 401


def test_upload_document_ok(client: TestClient, upload_root: Path):
    token = _token()
    res = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {token}"},
        data={"file_role": "document"},
        files={"file": ("policy.csv", b"title,body\nHello,World\n", "text/csv")},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["file_role"] == "document"
    assert body["client_id"] == str(DEMO_TENANT_ID)
    assert body["status"] == "queued"
    assert body["task_id"] == "task-test-1"
    assert (upload_root / body["relative_path"]).is_file()


def test_upload_without_enqueue(client: TestClient):
    token = _token()
    res = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {token}"},
        data={"file_role": "document", "enqueue": "false"},
        files={"file": ("policy.csv", b"title,body\nHello,World\n", "text/csv")},
    )
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "stored"
    assert res.json()["task_id"] is None


def test_upload_rejects_wrong_extension(client: TestClient):
    token = _token()
    res = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {token}"},
        data={"file_role": "document"},
        files={"file": ("export.zip", b"PK\x03\x04", "application/zip")},
    )
    assert res.status_code == 400


def test_upload_cross_tenant_denied(client: TestClient):
    token = _token(tenant_id=str(DEMO_TENANT_ID))
    other = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    res = client.post(
        "/uploads",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Client-Id": other,
        },
        data={"file_role": "document"},
        files={"file": ("a.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert res.status_code == 403

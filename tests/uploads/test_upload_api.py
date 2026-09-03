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


def test_agent_attachment_role_accepts_any_extension():
    """Non-ingested payloads carry no extension policy."""
    for name in ("chart.png", "clip.mp3", "bundle.tar.gz", "tool.exe", "README"):
        assert validate_upload_filename(FileRole.AGENT_ATTACHMENT, name)


def test_agent_attachment_role_still_sanitizes_filename():
    """Dropping the allowlist must not drop path-traversal protection."""
    safe = validate_upload_filename(
        FileRole.AGENT_ATTACHMENT, "../../etc/passwd.png"
    )
    assert safe == "passwd.png"
    assert "/" not in safe and "\\" not in safe and ".." not in safe


def test_ingesting_roles_keep_their_allowlists():
    """Loosening the agent role must not loosen parser-routed roles."""
    with pytest.raises(ValueError):
        validate_upload_filename(FileRole.DOCUMENT, "chart.png")
    with pytest.raises(ValueError):
        validate_upload_filename(FileRole.WORKFLOW, "chart.png")
    with pytest.raises(ValueError):
        validate_upload_filename(FileRole.SLACK_HISTORY, "chart.png")


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


def test_upload_dry_run_ingests_sync(
    client: TestClient, upload_root: Path, monkeypatch: pytest.MonkeyPatch
):
    from api.app.ingest.upload_ingest import UploadIngestResult

    captured: dict = {}

    def _fake_ingest(**kwargs):
        captured.update(kwargs)
        return UploadIngestResult(
            client_id=kwargs["client_id"],
            file_role=FileRole.DOCUMENT,
            filename=kwargs["filename"],
            unit_or_message_count=1,
            chunk_count=2,
            point_ids=["p1", "p2"],
        )

    monkeypatch.setattr("api.app.ingestion.routes.ingest_upload", _fake_ingest)
    monkeypatch.setattr(
        "api.app.ingestion.routes.require_entitlement",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "api.app.ingestion.routes.require_budget",
        lambda *_a, **_k: None,
    )
    app.dependency_overrides[get_settings] = lambda: Settings(
        upload_dir=str(upload_root),
        jwt_secret="test-secret-at-least-32-chars-long!",
    )

    token = _token()
    res = client.post(
        "/ingestion/dry-run",
        headers={"Authorization": f"Bearer {token}"},
        data={"file_role": "document"},
        files={"file": ("policy.csv", b"title,body\nHello,World\n", "text/csv")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "ingested"
    assert body["chunk_count"] == 2
    assert body["point_count"] == 2
    assert body["point_ids"] == ["p1", "p2"]
    assert body["file_role"] == "document"
    assert body["client_id"] == str(DEMO_TENANT_ID)
    assert (upload_root / body["relative_path"]).is_file()
    assert captured["relative_path"] == body["relative_path"]
    assert captured["filename"] == "policy.csv"


def test_upload_dry_run_requires_auth(client: TestClient):
    res = client.post(
        "/ingestion/dry-run",
        data={"file_role": "document"},
        files={"file": ("a.csv", b"x,y\n1,2\n", "text/csv")},
    )
    assert res.status_code == 401


def test_upload_dry_run_rejects_wrong_extension(
    client: TestClient, upload_root: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "api.app.ingestion.routes.require_entitlement",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "api.app.ingestion.routes.require_budget",
        lambda *_a, **_k: None,
    )
    app.dependency_overrides[get_settings] = lambda: Settings(
        upload_dir=str(upload_root),
        jwt_secret="test-secret-at-least-32-chars-long!",
    )
    token = _token()
    res = client.post(
        "/ingestion/dry-run",
        headers={"Authorization": f"Bearer {token}"},
        data={"file_role": "document"},
        files={"file": ("export.zip", b"PK\x03\x04", "application/zip")},
    )
    assert res.status_code == 400


def test_upload_dry_run_ingest_error_maps_to_502(
    client: TestClient, upload_root: Path, monkeypatch: pytest.MonkeyPatch
):
    def _boom(**_kwargs):
        raise RuntimeError("tei down")

    monkeypatch.setattr("api.app.ingestion.routes.ingest_upload", _boom)
    monkeypatch.setattr(
        "api.app.ingestion.routes.require_entitlement",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "api.app.ingestion.routes.require_budget",
        lambda *_a, **_k: None,
    )
    app.dependency_overrides[get_settings] = lambda: Settings(
        upload_dir=str(upload_root),
        jwt_secret="test-secret-at-least-32-chars-long!",
    )

    token = _token()
    res = client.post(
        "/ingestion/dry-run",
        headers={"Authorization": f"Bearer {token}"},
        data={"file_role": "document"},
        files={"file": ("policy.csv", b"title,body\nHello,World\n", "text/csv")},
    )
    assert res.status_code == 502
    assert res.json()["detail"] == "ingest_failed"

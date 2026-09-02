"""Tenant file listing API tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app.auth.tokens import create_access_token
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID, DEMO_OWNER_ID, DEMO_TENANT_ID
from api.app.settings import Settings, get_settings


@pytest.fixture
def upload_root(tmp_path: Path) -> Path:
    root = tmp_path / "uploads"
    root.mkdir()
    return root


@pytest.fixture
def client(upload_root: Path) -> TestClient:
    settings = Settings(
        upload_dir=str(upload_root),
        jwt_secret="test-secret-at-least-32-chars-long!",
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


def _write_tenant_file(upload_root: Path, client_id: str, rel: str, data: bytes = b"hello") -> Path:
    path = upload_root / client_id / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_tenant_files_requires_auth(client: TestClient):
    res = client.get("/tenant-files")
    assert res.status_code == 401


def test_tenant_files_empty_folder(client: TestClient, upload_root: Path):
    token = _token()
    res = client.get(
        "/tenant-files",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["client_id"] == str(DEMO_TENANT_ID)
    assert body["files"] == []
    assert body["truncated"] is False


def test_tenant_files_lists_nested_files(client: TestClient, upload_root: Path):
    cid = str(DEMO_TENANT_ID)
    _write_tenant_file(upload_root, cid, "top.csv", b"a,b\n1,2\n")
    _write_tenant_file(upload_root, cid, "workflows/template.txt", b"steps")
    _write_tenant_file(upload_root, cid, "nested/deep/report.pdf", b"%PDF")

    token = _token()
    res = client.get(
        "/tenant-files",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    paths = {item["relative_path"] for item in res.json()["files"]}
    assert paths == {"top.csv", "workflows/template.txt", "nested/deep/report.pdf"}


def test_tenant_files_prefix_filter(client: TestClient, upload_root: Path):
    cid = str(DEMO_TENANT_ID)
    _write_tenant_file(upload_root, cid, "top.csv")
    _write_tenant_file(upload_root, cid, "workflows/template.txt")

    token = _token()
    res = client.get(
        "/tenant-files?prefix=workflows",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    files = res.json()["files"]
    assert len(files) == 1
    assert files[0]["relative_path"] == "workflows/template.txt"


def test_tenant_files_cross_tenant_denied(client: TestClient):
    token = _token(tenant_id=str(DEMO_TENANT_ID))
    other = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    res = client.get(
        "/tenant-files",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Client-Id": other,
        },
    )
    assert res.status_code == 403


def test_tenant_files_platform_owner_with_client_id(
    client: TestClient, upload_root: Path
):
    cid = str(DEMO_TENANT_ID)
    _write_tenant_file(upload_root, cid, "owner-visible.txt", b"ok")

    token = _token(role="platform_owner")
    res = client.get(
        "/tenant-files",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Client-Id": cid,
        },
    )
    assert res.status_code == 200, res.text
    assert len(res.json()["files"]) == 1
    assert res.json()["files"][0]["filename"] == "owner-visible.txt"


def test_tenant_files_truncation_and_cursor(client: TestClient, upload_root: Path):
    cid = str(DEMO_TENANT_ID)
    _write_tenant_file(upload_root, cid, "a.txt")
    _write_tenant_file(upload_root, cid, "b.txt")
    _write_tenant_file(upload_root, cid, "c.txt")

    token = _token()
    res = client.get(
        "/tenant-files?limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["files"]) == 2
    assert body["truncated"] is True
    assert body["next_cursor"] == body["files"][-1]["relative_path"]

    res2 = client.get(
        f"/tenant-files?limit=2&cursor={body['next_cursor']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 200, res.text
    body2 = res2.json()
    assert len(body2["files"]) == 1
    assert body2["truncated"] is False


def test_tenant_files_rejects_bad_prefix(client: TestClient):
    token = _token()
    res = client.get(
        "/tenant-files?prefix=../etc",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400


def test_tenant_file_download_ok(client: TestClient, upload_root: Path):
    cid = str(DEMO_TENANT_ID)
    payload = b"download-me"
    _write_tenant_file(upload_root, cid, "nested/report.txt", payload)

    token = _token()
    res = client.get(
        "/tenant-files/content?key=nested/report.txt",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    assert res.content == payload
    assert "attachment" in (res.headers.get("content-disposition") or "").lower()


def test_tenant_file_download_not_found(client: TestClient):
    token = _token()
    res = client.get(
        "/tenant-files/content?key=missing.txt",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


def test_tenant_file_download_rejects_escape(client: TestClient, upload_root: Path):
    cid = str(DEMO_TENANT_ID)
    _write_tenant_file(upload_root, cid, "safe.txt")

    token = _token()
    res = client.get(
        "/tenant-files/content?key=../etc/passwd",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400


def test_tenant_file_download_cross_tenant_denied(client: TestClient, upload_root: Path):
    cid = str(DEMO_TENANT_ID)
    _write_tenant_file(upload_root, cid, "secret.txt", b"secret")

    token = _token(tenant_id=cid)
    other = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    res = client.get(
        "/tenant-files/content?key=secret.txt",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Client-Id": other,
        },
    )
    assert res.status_code == 403

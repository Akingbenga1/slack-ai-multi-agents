"""Ingest job status listing (Task 19.2)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from api.app.auth.tokens import create_access_token
from api.app.db.models import Job
from api.app.db.session import get_db
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID, DEMO_TENANT_ID
from api.app.settings import Settings, get_settings
from worker.job_meta import KIND_INGEST_UPLOAD, STATUS_SUCCEEDED


class _FakeResult:
    def __init__(self, rows: list[Job]):
        self._rows = rows

    def all(self) -> list[Job]:
        return self._rows


class _FakeScalars:
    def __init__(self, rows: list[Job]):
        self._rows = rows

    def all(self) -> list[Job]:
        return self._rows


class _FakeDb:
    def __init__(self, rows: list[Job]):
        self.rows = rows

    def scalars(self, _stmt):
        return _FakeScalars(self.rows)


@pytest.fixture
def jobs() -> list[Job]:
    now = datetime.now(timezone.utc)
    return [
        Job(
            id=uuid4(),
            tenant_id=DEMO_TENANT_ID,
            kind=KIND_INGEST_UPLOAD,
            status=STATUS_SUCCEEDED,
            payload={
                "upload_id": "up-1",
                "filename": "policy.csv",
                "file_role": "document",
                "celery_task_id": "t1",
            },
            result={"chunk_count": 2},
            created_at=now,
            finished_at=now,
        )
    ]


@pytest.fixture
def client(jobs: list[Job], monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    fake = _FakeDb(jobs)

    def _fake_db():
        yield fake

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = _fake_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _token() -> str:
    settings = Settings(jwt_secret="test-secret-at-least-32-chars-long!")
    return create_access_token(
        settings=settings,
        sub=str(DEMO_ADMIN_ID),
        email="admin@example.com",
        role="org_admin",
        tenant_id=str(DEMO_TENANT_ID),
    )


def test_list_ingest_jobs(client: TestClient):
    res = client.get(
        "/uploads/jobs",
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["client_id"] == str(DEMO_TENANT_ID)
    assert len(body["jobs"]) == 1
    assert body["jobs"][0]["filename"] == "policy.csv"
    assert body["jobs"][0]["status"] == STATUS_SUCCEEDED


def test_status_by_upload_id(client: TestClient):
    res = client.get(
        "/uploads/status/up-1",
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["upload_id"] == "up-1"


def test_status_missing(client: TestClient):
    res = client.get(
        "/uploads/status/missing",
        headers={"Authorization": f"Bearer {_token()}"},
    )
    assert res.status_code == 404


def test_jobs_cross_tenant_denied(client: TestClient):
    other = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    res = client.get(
        "/uploads/jobs",
        headers={
            "Authorization": f"Bearer {_token()}",
            "X-Client-Id": other,
        },
    )
    assert res.status_code == 403

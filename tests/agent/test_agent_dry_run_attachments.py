"""Tests for agent dry-run file attachment helpers + endpoint."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from api.app.agent.base import AgentResult
from api.app.agent.dry_run_files import (
    attachment_from_storage_relative_path,
    attachment_from_upload_bytes,
    attachment_from_upload_id,
    attachment_metadata,
)
from api.app.auth.tokens import create_access_token
from api.app.main import app
from api.app.membership import DEMO_ADMIN_ID, DEMO_TENANT_ID
from api.app.settings import Settings, get_settings


@pytest.fixture
def upload_root(tmp_path: Path) -> Path:
    root = tmp_path / "uploads"
    root.mkdir()
    return root


@pytest.fixture
def settings(upload_root: Path) -> Settings:
    return Settings(
        upload_dir=str(upload_root),
        jwt_secret="test-secret-at-least-32-chars-long!",
        llm_provider="stub",
    )


def _token() -> str:
    return create_access_token(
        settings=Settings(jwt_secret="test-secret-at-least-32-chars-long!"),
        sub=str(DEMO_ADMIN_ID),
        email="admin@example.com",
        role="org_admin",
        tenant_id=str(DEMO_TENANT_ID),
    )


def test_attachment_from_upload_bytes_sets_paths(settings: Settings):
    att = attachment_from_upload_bytes(
        client_id=str(DEMO_TENANT_ID),
        filename="user-document.pdf",
        data=b"%PDF-1.4 dry-run-test",
        content_type="application/pdf",
        settings=settings,
    )
    assert att["filename"] == "user-document.pdf"
    assert att["storage_relative_path"].startswith(f"{DEMO_TENANT_ID}/")
    assert att["storage_relative_path"].endswith("_user-document.pdf")
    assert att["local_path"]
    assert Path(att["local_path"]).is_file()
    assert att["upload_id"]


def test_attachment_from_upload_id_resolves(settings: Settings):
    stored = attachment_from_upload_bytes(
        client_id=str(DEMO_TENANT_ID),
        filename="note.txt",
        data=b"hello",
        settings=settings,
    )
    again = attachment_from_upload_id(
        client_id=str(DEMO_TENANT_ID),
        upload_id=stored["upload_id"],
        settings=settings,
    )
    assert again["storage_relative_path"] == stored["storage_relative_path"]
    assert Path(again["local_path"]).is_file()


def test_attachment_from_storage_relative_path(settings: Settings):
    stored = attachment_from_upload_bytes(
        client_id=str(DEMO_TENANT_ID),
        filename="doc.pdf",
        data=b"%PDF",
        settings=settings,
    )
    again = attachment_from_storage_relative_path(
        client_id=str(DEMO_TENANT_ID),
        storage_relative_path=stored["storage_relative_path"],
        settings=settings,
    )
    assert again["local_path"] == stored["local_path"]


def test_attachment_metadata_keeps_storage_and_local_path():
    meta = attachment_metadata(
        {
            "filename": "user-document.pdf",
            "mimetype": "application/pdf",
            "text": "MUST DROP",
            "storage_relative_path": f"{DEMO_TENANT_ID}/u_user-document.pdf",
            "local_path": r"C:\data\uploads\u_user-document.pdf",
            "upload_id": "u",
        }
    )
    assert meta["filename"] == "user-document.pdf"
    assert meta["storage_relative_path"].endswith("user-document.pdf")
    assert meta["local_path"].endswith("user-document.pdf")
    assert meta["upload_id"] == "u"
    assert "text" not in meta


@pytest.fixture
def client(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr("api.app.agent.routes.get_settings", lambda: settings)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_agent_dry_run_json_with_upload_id_passes_attachments(
    client: TestClient,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
):
    stored = attachment_from_upload_bytes(
        client_id=str(DEMO_TENANT_ID),
        filename="user-document.pdf",
        data=b"%PDF-1.4",
        settings=settings,
    )
    captured: dict = {}

    def _fake_plan_and_execute(**kwargs):
        captured.update(kwargs)
        return AgentResult(
            role="facade",
            client_id=str(DEMO_TENANT_ID),
            status="succeeded",
            message="ok",
            extra={
                "workflow": "document_summary",
                "plan_id": "11111111-1111-1111-1111-111111111111",
                "plan_steps": [],
            },
        )

    monkeypatch.setattr(
        "api.app.agent.facade.plan_and_execute",
        _fake_plan_and_execute,
    )

    res = client.post(
        "/agent/dry-run",
        headers={"Authorization": f"Bearer {_token()}"},
        json={
            "question": "Using the attached user-document.pdf, summarize it.",
            "include_trace": True,
            "upload_id": stored["upload_id"],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["attachment"]["upload_id"] == stored["upload_id"]
    assert body["attachment"]["storage_relative_path"] == stored["storage_relative_path"]
    assert body["attachment"]["local_path"]
    assert captured["attachments"]
    assert captured["attachments"][0]["local_path"] == stored["local_path"]


def test_agent_dry_run_multipart_file_stores_and_attaches(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict = {}

    def _fake_plan_and_execute(**kwargs):
        captured.update(kwargs)
        return AgentResult(
            role="facade",
            client_id=str(DEMO_TENANT_ID),
            status="succeeded",
            message="ok",
            extra={"workflow": "qa", "plan_id": str(UUID(int=1))},
        )

    monkeypatch.setattr(
        "api.app.agent.facade.plan_and_execute",
        _fake_plan_and_execute,
    )

    res = client.post(
        "/agent/dry-run",
        headers={"Authorization": f"Bearer {_token()}"},
        data={
            "question": "Summarize the attached PDF into a new PDF.",
            "include_trace": "true",
        },
        files={
            "file": ("user-document.pdf", b"%PDF-1.4 hello", "application/pdf"),
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["attachment"]["filename"] == "user-document.pdf"
    assert body["attachment"]["local_path"]
    assert Path(body["attachment"]["local_path"]).is_file()
    assert captured["attachments"][0]["storage_relative_path"]


def test_agent_dry_run_multipart_multiple_files_stores_and_attaches(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict = {}

    def _fake_plan_and_execute(**kwargs):
        captured.update(kwargs)
        return AgentResult(
            role="facade",
            client_id=str(DEMO_TENANT_ID),
            status="succeeded",
            message="ok",
            extra={"workflow": "qa", "plan_id": str(UUID(int=2))},
        )

    monkeypatch.setattr(
        "api.app.agent.facade.plan_and_execute",
        _fake_plan_and_execute,
    )

    res = client.post(
        "/agent/dry-run",
        headers={"Authorization": f"Bearer {_token()}"},
        data={
            "question": "Compare the two attached PDFs.",
            "include_trace": "true",
        },
        files=[
            ("file", ("alpha.pdf", b"%PDF-1.4 alpha", "application/pdf")),
            ("file", ("beta.pdf", b"%PDF-1.4 beta", "application/pdf")),
        ],
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["attachments"]) == 2
    assert body["attachments"][0]["filename"] == "alpha.pdf"
    assert body["attachments"][1]["filename"] == "beta.pdf"
    assert body["attachment"]["filename"] == "alpha.pdf"
    assert len(captured["attachments"]) == 2
    assert captured["attachments"][0]["filename"] == "alpha.pdf"
    assert captured["attachments"][1]["filename"] == "beta.pdf"


def test_agent_dry_run_multipart_accepts_non_document_file_types(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Dry-run attachments are opaque executor payloads, not ingested docs."""
    captured: dict = {}

    def _fake_plan_and_execute(**kwargs):
        captured.update(kwargs)
        return AgentResult(
            role="facade",
            client_id=str(DEMO_TENANT_ID),
            status="succeeded",
            message="ok",
            extra={"workflow": "image_processing", "plan_id": str(UUID(int=4))},
        )

    monkeypatch.setattr(
        "api.app.agent.facade.plan_and_execute",
        _fake_plan_and_execute,
    )

    res = client.post(
        "/agent/dry-run",
        headers={"Authorization": f"Bearer {_token()}"},
        data={"question": "Combine the attached files into one image."},
        files=[
            ("file", ("a.png", b"\x89PNG\r\n\x1a\n alpha", "image/png")),
            ("file", ("b.jpg", b"\xff\xd8\xff beta", "image/jpeg")),
            ("file", ("c.bin", b"\x00\x01\x02 gamma", "application/octet-stream")),
        ],
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert [item["filename"] for item in body["attachments"]] == [
        "a.png",
        "b.jpg",
        "c.bin",
    ]
    for item in body["attachments"]:
        assert Path(item["local_path"]).is_file()
    assert len(captured["attachments"]) == 3


def test_attachment_from_upload_bytes_accepts_binary_payload(settings: Settings):
    att = attachment_from_upload_bytes(
        client_id=str(DEMO_TENANT_ID),
        filename="chart.png",
        data=b"\x89PNG\r\n\x1a\n",
        content_type="image/png",
        settings=settings,
    )
    assert att["filename"] == "chart.png"
    assert Path(att["local_path"]).is_file()
    assert Path(att["local_path"]).read_bytes() == b"\x89PNG\r\n\x1a\n"


def test_agent_dry_run_json_with_upload_ids_passes_all_attachments(
    client: TestClient,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
):
    first = attachment_from_upload_bytes(
        client_id=str(DEMO_TENANT_ID),
        filename="alpha.pdf",
        data=b"%PDF-1.4 alpha",
        settings=settings,
    )
    second = attachment_from_upload_bytes(
        client_id=str(DEMO_TENANT_ID),
        filename="beta.pdf",
        data=b"%PDF-1.4 beta",
        settings=settings,
    )
    captured: dict = {}

    def _fake_plan_and_execute(**kwargs):
        captured.update(kwargs)
        return AgentResult(
            role="facade",
            client_id=str(DEMO_TENANT_ID),
            status="succeeded",
            message="ok",
            extra={"workflow": "document_summary", "plan_id": str(UUID(int=3))},
        )

    monkeypatch.setattr(
        "api.app.agent.facade.plan_and_execute",
        _fake_plan_and_execute,
    )

    res = client.post(
        "/agent/dry-run",
        headers={"Authorization": f"Bearer {_token()}"},
        json={
            "question": "Compare both attached PDFs.",
            "upload_ids": [first["upload_id"], second["upload_id"]],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["attachments"]) == 2
    assert {item["upload_id"] for item in body["attachments"]} == {
        first["upload_id"],
        second["upload_id"],
    }
    assert len(captured["attachments"]) == 2


def test_agent_dry_run_rejects_mixed_multipart_attachment_sources(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "api.app.agent.facade.plan_and_execute",
        MagicMock(side_effect=AssertionError("must not run")),
    )
    res = client.post(
        "/agent/dry-run",
        headers={"Authorization": f"Bearer {_token()}"},
        data={
            "question": "Compare files",
            "upload_id": "00000000-0000-0000-0000-000000000001",
        },
        files={
            "file": ("alpha.pdf", b"%PDF-1.4", "application/pdf"),
        },
    )
    assert res.status_code == 400


def test_agent_dry_run_rejects_unknown_upload_id(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "api.app.agent.facade.plan_and_execute",
        MagicMock(side_effect=AssertionError("must not run")),
    )
    res = client.post(
        "/agent/dry-run",
        headers={"Authorization": f"Bearer {_token()}"},
        json={
            "question": "Summarize attached file",
            "upload_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert res.status_code == 400

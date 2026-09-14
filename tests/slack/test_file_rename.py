"""Slack file rename helpers (Sprint 23.4)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from api.app.slack.file_actions import (
    parse_requested_filename,
    rename_slack_file_or_copy,
    rename_stored_org_copy,
)
from api.app.uploads.storage import store_upload
from api.app.uploads.roles import FileRole

_RealClient = httpx.Client


def test_parse_requested_filename():
    assert (
        parse_requested_filename("Please rename the file to Q3-final.pdf")
        == "Q3-final.pdf"
    )
    assert parse_requested_filename(
        "rename it as financial_report_v2.csv",
        fallback_from="old.csv",
    ) == "financial_report_v2.csv"
    assert parse_requested_filename(
        "rename the file",
        fallback_from="report.csv",
    ) == "report_renamed.csv"


def test_rename_stored_org_copy_isolates_tenant(tmp_path: Path):
    cid_a = str(uuid4())
    cid_b = str(uuid4())
    stored = store_upload(
        upload_root=tmp_path,
        client_id=cid_a,
        file_role=FileRole.DOCUMENT,
        filename="report.csv",
        data=b"a,b\n1,2\n",
        content_type="text/csv",
    )
    result = rename_stored_org_copy(
        client_id=cid_a,
        upload_root=tmp_path,
        stored_relative_path=stored.relative_path,
        new_filename="Q3-final.csv",
    )
    assert result["ok"] is True
    assert result["new_filename"] == "Q3-final.csv"
    assert (tmp_path / result["stored_relative_path"]).is_file()
    assert not (tmp_path / stored.relative_path).exists()

    with pytest.raises(ValueError, match="not under this tenant"):
        rename_stored_org_copy(
            client_id=cid_b,
            upload_root=tmp_path,
            stored_relative_path=result["stored_relative_path"],
            new_filename="stolen.csv",
        )


def test_rename_slack_file_or_copy_org_and_slack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    cid = str(uuid4())
    stored = store_upload(
        upload_root=tmp_path,
        client_id=cid,
        file_role=FileRole.DOCUMENT,
        filename="report.csv",
        data=b"competitor,share\nAcme,40\n",
        content_type="text/csv",
    )
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.method == "POST"
        assert request.url.path.endswith("/files.edit")
        return httpx.Response(200, json={"ok": True, "file": {"id": "FSRC", "title": "Q3-final.csv"}})

    transport = httpx.MockTransport(handler)

    def factory(*args, **kwargs):
        kwargs = {**kwargs, "transport": transport}
        return _RealClient(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)

    from api.app.slack.client import SlackWebClient

    client = SlackWebClient("xoxb-test", sleep=lambda _: None)
    result = rename_slack_file_or_copy(
        client_id=cid,
        upload_root=tmp_path,
        question="rename the file to Q3-final.csv",
        attached_evidence=[
            {
                "client_id": cid,
                "file_id": "FSRC",
                "filename": "report.csv",
                "text": "x",
                "stored_relative_path": stored.relative_path,
            }
        ],
        bot_token="xoxb-test",
        slack_client=client,
    )
    assert result["ok"] is True
    assert result["mode"] == "org_and_slack"
    assert "Q3-final.csv" in result["confirmation"]
    assert any(p.endswith("/files.edit") for p in calls)


def test_rename_fail_closed_blank_client(tmp_path: Path):
    with pytest.raises(ValueError, match="client_id"):
        rename_slack_file_or_copy(
            client_id="",
            upload_root=tmp_path,
            new_filename="x.csv",
        )

"""Sprint 23.5 — isolation, usage types, and J10 offline smoke."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from api.app.governance.usage import (
    EVENT_FILE_JOB,
    EVENT_FILE_RENAME,
    EVENT_PDF_GENERATE,
    JOB_BUDGET_EVENT_TYPES,
)
from api.app.slack.attachments import intake_attachments, require_client_id
from api.app.slack.file_actions import (
    produce_and_upload_analysis_pdf,
    rename_slack_file_or_copy,
)
from api.app.uploads.roles import FileRole
from api.app.uploads.storage import store_upload

_RealClient = httpx.Client


def test_usage_event_types_include_file_actions():
    assert EVENT_FILE_JOB in JOB_BUDGET_EVENT_TYPES
    assert EVENT_PDF_GENERATE in JOB_BUDGET_EVENT_TYPES
    assert EVENT_FILE_RENAME in JOB_BUDGET_EVENT_TYPES


def test_require_client_id_fail_closed():
    with pytest.raises(ValueError, match="client_id"):
        require_client_id("")
    with pytest.raises(ValueError, match="client_id"):
        require_client_id("   ")


def test_j10_offline_smoke_attach_pdf_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """
    Financial report attach → PDF competitor analysis → rename org copy.

    Slack HTTP is mocked; proves isolation + deliverable paths without a live
    workspace (live scopes remain Needs-human).
    """
    cid = str(uuid4())
    other = str(uuid4())

    # Tenant-scoped store of the "attached" financial report
    source = store_upload(
        upload_root=tmp_path,
        client_id=cid,
        file_role=FileRole.DOCUMENT,
        filename="financial_report.csv",
        data=b"competitor,share\nAcme,42\nBeta,30\n",
        content_type="text/csv",
    )

    upload_calls: list[str] = []
    edit_calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/files.upload"):
            upload_calls.append(path)
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "file": {
                        "id": "FPDF1",
                        "permalink": "https://slack.com/files/FPDF1",
                        "name": "competitor_analysis.pdf",
                    },
                },
            )
        if path.endswith("/files.edit"):
            edit_calls.append(path)
            return httpx.Response(
                200,
                json={"ok": True, "file": {"id": "FSRC", "title": "Q3-financial.csv"}},
            )
        return httpx.Response(404, json={"ok": False, "error": "unknown_method"})

    transport = httpx.MockTransport(handler)

    def factory(*args, **kwargs):
        kwargs = {**kwargs, "transport": transport}
        return _RealClient(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)

    from api.app.slack.client import SlackWebClient

    client = SlackWebClient("xoxb-test", sleep=lambda _: None)
    evidence = [
        {
            "client_id": cid,
            "file_id": "FSRC",
            "filename": "financial_report.csv",
            "text": "competitor,share\nAcme,42\nBeta,30\n",
            "stored_relative_path": source.relative_path,
        }
    ]

    pdf = produce_and_upload_analysis_pdf(
        client_id=cid,
        bot_token="xoxb-test",
        channel="C123",
        analysis_text="Acme leads share at 42%; Beta trails at 30%.",
        attached_evidence=evidence,
        upload_root=tmp_path,
        slack_client=client,
    )
    assert pdf["ok"] is True
    assert pdf["client_id"] == cid
    assert upload_calls

    # Cross-tenant PDF attempt must not use other tenant's evidence as source name
    # (usable evidence filtered by client_id); blank client_id still fail-closed.
    with pytest.raises(ValueError, match="client_id"):
        produce_and_upload_analysis_pdf(
            client_id="",
            bot_token="xoxb",
            channel="C1",
            analysis_text="x",
            attached_evidence=evidence,
            upload_root=tmp_path,
        )

    rename = rename_slack_file_or_copy(
        client_id=cid,
        upload_root=tmp_path,
        question="rename the financial report file to Q3-financial.csv",
        attached_evidence=evidence,
        bot_token="xoxb-test",
        slack_client=client,
    )
    assert rename["ok"] is True
    assert rename["new_filename"] == "Q3-financial.csv"
    assert (tmp_path / rename["stored_relative_path"]).is_file()
    assert edit_calls

    # Other tenant cannot rename this org copy (fail-closed, no raise to caller)
    stolen = rename_slack_file_or_copy(
        client_id=other,
        upload_root=tmp_path,
        new_filename="stolen.csv",
        stored_relative_path=rename["stored_relative_path"],
    )
    assert stolen["ok"] is False
    assert "not under this tenant" in str(stolen.get("error") or "")
    # Original tenant file still present under cid path
    assert (tmp_path / rename["stored_relative_path"]).is_file()
    assert not (tmp_path / other / "stolen.csv").exists()


def test_intake_fail_closed_blank_client(tmp_path: Path):
    with pytest.raises(ValueError, match="client_id"):
        intake_attachments(
            client_id="",
            bot_token="xoxb",
            event={"files": [{"id": "F1", "name": "a.csv"}]},
            upload_root=tmp_path,
        )

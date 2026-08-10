"""Slack attachment intake (Sprint 23.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from api.app.slack.attachments import (
    evidence_to_chunks,
    files_from_event,
    intake_attachments,
    require_client_id,
)
from api.app.slack.client import SlackWebClient

_RealClient = httpx.Client


def test_require_client_id_fail_closed():
    with pytest.raises(ValueError, match="client_id"):
        require_client_id("")
    with pytest.raises(ValueError, match="client_id"):
        require_client_id("   ")


def test_files_from_event_files_array_and_text():
    event = {
        "text": "<@Ubot> analyse https://files.slack.com/files-pri/T1/F999ABCDEF/report.pdf and F888XYZABC12",
        "files": [
            {
                "id": "F111AAAAAA",
                "name": "fin.csv",
                "mimetype": "text/csv",
                "url_private_download": "https://files.slack.com/download/F111",
            }
        ],
    }
    refs = files_from_event(event)
    ids = {r.file_id for r in refs}
    assert "F111AAAAAA" in ids
    assert "F999ABCDEF" in ids
    assert "F888XYZABC12" in ids
    primary = next(r for r in refs if r.file_id == "F111AAAAAA")
    assert primary.name == "fin.csv"
    assert primary.url_private_download.endswith("F111")


def test_intake_attachments_parses_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cid = str(uuid4())
    csv_bytes = b"competitor,share\nAcme,40\nBeta,25\n"
    event = {
        "text": "analyse this",
        "files": [
            {
                "id": "FCSV000001",
                "name": "report.csv",
                "mimetype": "text/csv",
                "url_private_download": "https://files.slack.com/download/FCSV",
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if "download" in str(request.url):
            assert request.headers.get("Authorization") == "Bearer xoxb-test"
            return httpx.Response(200, content=csv_bytes)
        return httpx.Response(404, json={"ok": False})

    transport = httpx.MockTransport(handler)

    def factory(*args, **kwargs):
        kwargs = {**kwargs, "transport": transport}
        return _RealClient(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)

    client = SlackWebClient("xoxb-test", sleep=lambda _: None)
    result = intake_attachments(
        client_id=cid,
        bot_token="xoxb-test",
        event=event,
        upload_root=tmp_path,
        slack_client=client,
    )
    assert len(result.evidence) == 1
    ev = result.evidence[0]
    assert ev.client_id == cid
    assert "Acme" in ev.text
    assert ev.stored_relative_path and ev.stored_relative_path.startswith(cid)
    assert (tmp_path / ev.stored_relative_path).is_file()

    chunks = evidence_to_chunks(result.evidence, client_id=cid)
    assert len(chunks) == 1
    assert chunks[0]["kind"] == "attachment"
    assert chunks[0]["client_id"] == cid


def test_intake_rejects_blank_client(tmp_path: Path):
    with pytest.raises(ValueError, match="client_id"):
        intake_attachments(
            client_id="",
            bot_token="xoxb-test",
            event={"files": [{"id": "F1"}]},
            upload_root=tmp_path,
        )


def test_evidence_to_chunks_drops_foreign_tenant():
    cid = str(uuid4())
    other = str(uuid4())
    chunks = evidence_to_chunks(
        [
            {
                "client_id": other,
                "text": "secret",
                "file_id": "F1",
                "filename": "x.csv",
            },
            {
                "client_id": cid,
                "text": "ok",
                "file_id": "F2",
                "filename": "y.csv",
            },
        ],
        client_id=cid,
    )
    assert len(chunks) == 1
    assert chunks[0]["text"] == "ok"

"""PDF export + Slack upload helpers (Sprint 23.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from api.app.slack.file_actions import produce_and_upload_analysis_pdf
from api.app.slack.pdf_export import analysis_to_pdf_bytes, default_pdf_filename

_RealClient = httpx.Client


def test_analysis_to_pdf_bytes_nonempty():
    data = analysis_to_pdf_bytes(
        title="Competitor analysis",
        body="*Acme* leads share.\n\nBeta is catching up.",
        subtitle="Source: report.csv",
    )
    assert data[:4] == b"%PDF"
    assert len(data) > 200


def test_default_pdf_filename():
    assert default_pdf_filename(source_filename="Q3 report.csv").endswith(".pdf")
    assert "Q3" in default_pdf_filename(source_filename="Q3 report.csv")


def test_produce_and_upload_analysis_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cid = str(uuid4())
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "POST"
        assert request.url.path.endswith("/files.upload")
        return httpx.Response(
            200,
            json={
                "ok": True,
                "file": {
                    "id": "FPDF1",
                    "permalink": "https://slack.com/files/FPDF1",
                    "name": "competitor_analysis_report.pdf",
                },
            },
        )

    transport = httpx.MockTransport(handler)

    def factory(*args, **kwargs):
        kwargs = {**kwargs, "transport": transport}
        return _RealClient(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)

    from api.app.slack.client import SlackWebClient

    client = SlackWebClient("xoxb-test", sleep=lambda _: None)
    result = produce_and_upload_analysis_pdf(
        client_id=cid,
        bot_token="xoxb-test",
        channel="C123",
        analysis_text="Acme vs Beta — Acme stronger in APAC.",
        attached_evidence=[
            {
                "client_id": cid,
                "file_id": "FSRC",
                "filename": "report.csv",
                "text": "competitor,share\nAcme,40",
            }
        ],
        upload_root=tmp_path,
        thread_ts="1.0",
        slack_client=client,
    )
    assert result["ok"] is True
    assert result["slack_file_id"] == "FPDF1"
    assert "open PDF" in result["confirmation"]
    assert result["stored_relative_path"]
    assert (tmp_path / result["stored_relative_path"]).is_file()
    assert len(calls) == 1


def test_produce_pdf_fail_closed_blank_client(tmp_path: Path):
    with pytest.raises(ValueError, match="client_id"):
        produce_and_upload_analysis_pdf(
            client_id="",
            bot_token="xoxb",
            channel="C1",
            analysis_text="x",
            attached_evidence=[],
            upload_root=tmp_path,
        )

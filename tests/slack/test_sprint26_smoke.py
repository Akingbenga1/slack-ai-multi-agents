"""Sprint 26.4 — Slack delivery Strategy smoke / regression (offline)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.billing.plans import apply_plan_state
from api.app.db.models import BillingCustomer, Tenant, UsageEvent, WorkflowTemplate
from api.app.settings import Settings
from api.app.slack.agent_reply import process_agent_reply
from api.app.slack.delivery import (
    AdviseDeliveryStrategy,
    DefaultPostStrategy,
    LibraryConfirmStrategy,
    PdfUploadStrategy,
    RenameDeliveryStrategy,
    get_delivery_strategy,
)
from api.app.slack.files import IntakeResult
from api.app.slack.files.refs import AttachedEvidence


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):  # noqa: ANN001
    return "TEXT"


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Tenant.__table__.create(engine)
    BillingCustomer.__table__.create(engine)
    UsageEvent.__table__.create(engine)
    WorkflowTemplate.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class _NoCloseSession:
    def __init__(self, inner: Session):
        self._inner = inner

    def __getattr__(self, name: str):
        return getattr(self._inner, name)

    def close(self) -> None:
        return None


def _tenant_active(db: Session) -> Tenant:
    t = Tenant(id=uuid4(), slug=f"s26-{uuid4().hex[:8]}", name="S26", status="active")
    db.add(t)
    db.flush()
    row = BillingCustomer(
        tenant_id=t.id,
        stripe_customer_id=f"cus_{uuid4().hex[:8]}",
        plan_status="inactive",
        entitlements={},
    )
    db.add(row)
    db.flush()
    apply_plan_state(db, row, plan_status="active", stripe_subscription_id="sub_s26")
    db.commit()
    return t


def test_delivery_strategy_map_swappable():
    assert isinstance(get_delivery_strategy("qa"), DefaultPostStrategy)
    assert isinstance(get_delivery_strategy("file_pdf_export"), PdfUploadStrategy)
    assert isinstance(get_delivery_strategy("file_rename"), RenameDeliveryStrategy)
    assert isinstance(get_delivery_strategy("workflow_store"), LibraryConfirmStrategy)
    assert isinstance(get_delivery_strategy("workflow_list"), LibraryConfirmStrategy)
    assert isinstance(get_delivery_strategy("workflow_advise"), AdviseDeliveryStrategy)


def test_files_facade_and_client_adapter_importable():
    from api.app.slack import files as files_pkg
    from api.app.slack.client import SlackWebClient
    from api.app.slack.store import client_for_team, client_for_tenant

    assert callable(files_pkg.intake_attachments)
    assert callable(files_pkg.produce_and_upload_analysis_pdf)
    assert callable(files_pkg.rename_slack_file_or_copy)
    assert callable(client_for_tenant)
    assert callable(client_for_team)
    assert callable(SlackWebClient.files_upload)
    assert not hasattr(SlackWebClient, "client_for_tenant")


def test_mention_grounded_reply_default_strategy(db: Session):
    t = _tenant_active(db)
    posts: list[dict] = []

    result = process_agent_reply(
        tenant_id=t.id,
        bot_token="xoxb-test",
        event={
            "type": "app_mention",
            "channel": "C1",
            "ts": "200.1",
            "text": "<@UBOT> refund policy",
        },
        team_id="T1",
        settings=Settings(agent_checkpointer="memory", anthropic_api_key=""),
        db_factory=lambda: _NoCloseSession(db),
        run_agent_fn=lambda **kwargs: {
            "answer": "Refunds within 30 days.",
            "retrieved_chunks": [{"label": "policy.md", "kind": "document"}],
            "hedge": False,
            "workflow": "qa",
            "usage_tokens": 8,
        },
        post_fn=lambda **kw: posts.append(kw) or {"ok": True},
    )
    assert result["ok"] is True
    assert result["denied"] is False
    assert result["workflow"] == "qa"
    assert "Refunds within 30 days." in posts[0]["text"]
    assert "*Sources:*" in posts[0]["text"]


def test_dm_grounded_reply_default_strategy(db: Session):
    t = _tenant_active(db)
    posts: list[dict] = []

    result = process_agent_reply(
        tenant_id=t.id,
        bot_token="xoxb-test",
        event={
            "type": "message",
            "channel_type": "im",
            "channel": "D1",
            "text": "shipping SLA",
        },
        settings=Settings(agent_checkpointer="memory", anthropic_api_key=""),
        db_factory=lambda: _NoCloseSession(db),
        run_agent_fn=lambda **_: {
            "answer": "Ships in 2 days.",
            "retrieved_chunks": [],
            "hedge": False,
            "workflow": "qa",
            "usage_tokens": 3,
        },
        post_fn=lambda **kw: posts.append(kw) or {"ok": True},
    )
    assert result["ok"] is True
    assert "Ships in 2 days." in posts[0]["text"]
    assert posts[0].get("thread_ts") is None


def test_pdf_delivery_path_via_pipeline(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    t = _tenant_active(db)
    cid = str(t.id)
    posts: list[dict] = []
    pdf_calls: list[dict] = []

    ev = AttachedEvidence(
        client_id=cid,
        file_id="F1",
        filename="financial_report.csv",
        text="competitor,share\nAcme,42\n",
        stored_relative_path=f"{cid}/documents/financial_report.csv",
        mimetype="text/csv",
    )
    monkeypatch.setattr(
        "api.app.slack.reply_pipeline.intake_attachments",
        lambda **_kw: IntakeResult(refs=[], evidence=[ev], errors=[]),
    )
    monkeypatch.setattr(
        "api.app.slack.delivery.strategies.produce_and_upload_analysis_pdf",
        lambda **kwargs: pdf_calls.append(kwargs)
        or {
            "ok": True,
            "confirmation": "Uploaded competitor_analysis.pdf",
            "filename": "competitor_analysis.pdf",
            "file_id": "FPDF1",
        },
    )
    monkeypatch.setattr(
        "api.app.slack.delivery.strategies.rename_slack_file_or_copy",
        lambda **_kw: {
            "ok": True,
            "confirmation": "Renamed to Q3-financial.csv",
            "new_filename": "Q3-financial.csv",
            "stored_relative_path": f"{cid}/documents/Q3-financial.csv",
            "mode": "org_copy",
        },
    )

    result = process_agent_reply(
        tenant_id=t.id,
        bot_token="xoxb-test",
        event={
            "type": "app_mention",
            "channel": "C1",
            "user": "U1",
            "ts": "300.1",
            "text": (
                "<@UBOT> Produce a PDF of competitor analysis from this report "
                "and rename the financial report file to Q3-financial.csv"
            ),
            "files": [{"id": "F1", "name": "financial_report.csv"}],
        },
        team_id="T1",
        settings=Settings(
            agent_checkpointer="memory",
            anthropic_api_key="",
            upload_dir=str(tmp_path),
        ),
        db_factory=lambda: _NoCloseSession(db),
        run_agent_fn=lambda **_: {
            "answer": "Acme leads share.",
            "retrieved_chunks": [
                {"label": "financial_report.csv", "kind": "attachment", "text": "Acme"}
            ],
            "hedge": False,
            "workflow": "file_pdf_export",
            "usage_tokens": 20,
        },
        post_fn=lambda **kw: posts.append(kw) or {"ok": True},
    )
    assert result["ok"] is True
    assert result["workflow"] == "file_pdf_export"
    assert result["file_action"]["ok"] is True
    assert result["rename_action"]["ok"] is True
    assert len(pdf_calls) == 1
    assert "Acme leads share." in posts[0]["text"]
    assert "Uploaded competitor_analysis.pdf" in posts[0]["text"]
    assert "Renamed to Q3-financial.csv" in posts[0]["text"]


def test_rename_delivery_path_via_pipeline(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    t = _tenant_active(db)
    cid = str(t.id)
    posts: list[dict] = []

    ev = AttachedEvidence(
        client_id=cid,
        file_id="F2",
        filename="notes.txt",
        text="hello",
        stored_relative_path=f"{cid}/documents/notes.txt",
        mimetype="text/plain",
    )
    monkeypatch.setattr(
        "api.app.slack.reply_pipeline.intake_attachments",
        lambda **_kw: IntakeResult(refs=[], evidence=[ev], errors=[]),
    )
    monkeypatch.setattr(
        "api.app.slack.delivery.strategies.rename_slack_file_or_copy",
        lambda **_kw: {
            "ok": True,
            "confirmation": "Renamed to final-notes.txt",
            "new_filename": "final-notes.txt",
            "stored_relative_path": f"{cid}/documents/final-notes.txt",
            "mode": "org_copy",
        },
    )

    result = process_agent_reply(
        tenant_id=t.id,
        bot_token="xoxb-test",
        event={
            "type": "app_mention",
            "channel": "C1",
            "user": "U1",
            "ts": "301.1",
            "text": "<@UBOT> Please rename the file to final-notes.txt",
            "files": [{"id": "F2", "name": "notes.txt"}],
        },
        settings=Settings(
            agent_checkpointer="memory",
            anthropic_api_key="",
            upload_dir=str(tmp_path),
        ),
        db_factory=lambda: _NoCloseSession(db),
        run_agent_fn=lambda **_: {
            "answer": "Done.",
            "retrieved_chunks": [],
            "hedge": False,
            "workflow": "file_rename",
            "usage_tokens": 4,
        },
        post_fn=lambda **kw: posts.append(kw) or {"ok": True},
    )
    assert result["ok"] is True
    assert result["workflow"] == "file_rename"
    assert result["rename_action"]["ok"] is True
    assert "Renamed to final-notes.txt" in posts[0]["text"]


def test_library_list_confirm_skips_agent(db: Session, tmp_path: Path):
    t = _tenant_active(db)
    posts: list[dict] = []
    called = {"agent": False}

    def fake_run_agent(**_kwargs):
        called["agent"] = True
        return {}

    result = process_agent_reply(
        tenant_id=t.id,
        bot_token="xoxb-test",
        event={
            "type": "app_mention",
            "channel": "C1",
            "user": "U1",
            "ts": "400.1",
            "text": "<@UBOT> list shared workflows",
        },
        settings=Settings(
            agent_checkpointer="memory",
            anthropic_api_key="",
            upload_dir=str(tmp_path),
        ),
        db_factory=lambda: _NoCloseSession(db),
        run_agent_fn=fake_run_agent,
        post_fn=lambda **kw: posts.append(kw) or {"ok": True},
    )
    assert called["agent"] is False
    assert result["ok"] is True
    assert result["workflow"] == "workflow_list"
    assert result["workflow_action"]["ok"] is True
    assert "library" in posts[0]["text"].lower() or "workflow" in posts[0]["text"].lower()


def test_library_store_confirm_via_pipeline(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    t = _tenant_active(db)
    cid = str(t.id)
    posts: list[dict] = []
    body = "# Triage\n1. Ack\n2. Assign\n"
    rel = f"{cid}/documents/triage.md"
    (tmp_path / cid / "documents").mkdir(parents=True, exist_ok=True)
    (tmp_path / cid / "documents" / "triage.md").write_text(body, encoding="utf-8")

    ev = AttachedEvidence(
        client_id=cid,
        file_id="FSTORE",
        filename="triage.md",
        text=body,
        stored_relative_path=rel,
        mimetype="text/markdown",
    )
    monkeypatch.setattr(
        "api.app.slack.reply_pipeline.intake_attachments",
        lambda **_kw: IntakeResult(refs=[], evidence=[ev], errors=[]),
    )

    result = process_agent_reply(
        tenant_id=t.id,
        bot_token="xoxb-test",
        event={
            "type": "app_mention",
            "channel": "C1",
            "user": "U_UPLOADER",
            "ts": "401.1",
            "text": "<@UBOT> Store this workflow for colleagues",
            "files": [{"id": "FSTORE", "name": "triage.md"}],
        },
        settings=Settings(
            agent_checkpointer="memory",
            anthropic_api_key="",
            upload_dir=str(tmp_path),
        ),
        db_factory=lambda: _NoCloseSession(db),
        run_agent_fn=lambda **_: (_ for _ in ()).throw(AssertionError("agent")),
        post_fn=lambda **kw: posts.append(kw) or {"ok": True},
    )
    assert result["ok"] is True
    assert result["workflow"] == "workflow_store"
    assert result["workflow_action"]["ok"] is True
    assert "/app/workflows" in posts[0]["text"]
    assert "copy" in posts[0]["text"].lower()

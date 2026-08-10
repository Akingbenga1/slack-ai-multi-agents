"""Sprint 24.5 — J11 offline smoke: store → colleague copy → advice."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.agent.llm import StubChatModel
from api.app.agent.nodes.route import (
    classify_workflow,
    question_requests_workflow_advice,
)
from api.app.agent.run import run_agent
from api.app.db.models import Tenant, WorkflowTemplate
from api.app.retrieval.types import KnowledgeSearchResult
from api.app.settings import Settings
from api.app.slack.workflow_actions import (
    MSG_STORE_OK,
    copy_workflow_for_slack,
    enrich_evidence_for_advice,
    list_workflows_for_slack,
    store_workflow_from_slack,
)
from api.app.workflows.library import get_template, store_workflow_template


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
    WorkflowTemplate.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def tenant(db: Session) -> Tenant:
    t = Tenant(id=uuid4(), slug=f"j11-{uuid4().hex[:8]}", name="J11", status="active")
    db.add(t)
    db.commit()
    return t


def test_store_confirmation_mentions_library_and_copy():
    text = MSG_STORE_OK.format(title="Demo", template_id="11111111-1111-1111-1111-111111111111")
    assert "/app/workflows" in text
    assert "copy workflow" in text.lower()
    assert "advise" in text.lower()


def test_j11_combined_phrasing_store_plus_advise():
    q = (
        "I'll describe a new workflow in a file and upload it. "
        "Store it for colleagues to use and copy for their own modification, "
        "and advise how we can make this workflow work."
    )
    assert classify_workflow(q, has_attachments=True) == "workflow_store"
    assert question_requests_workflow_advice(q) is True


def test_j11_offline_smoke_store_copy_advice(
    db: Session, tenant: Tenant, tmp_path: Path
):
    """
    Channel upload → store → colleague copy → file-grounded advice.

    Offline (no live Slack); live scopes remain Needs-human.
    """
    cid = str(tenant.id)
    body = (
        b"# Incident triage workflow\n"
        b"1. Acknowledge in #incidents within 5 minutes\n"
        b"2. Assign severity and owner\n"
        b"3. Post status updates every 30 minutes\n"
        b"4. Write blameless retro within 48h\n"
    )

    # Seed as if Sprint 23.1 already stored the attachment under the tenant
    seed = store_workflow_template(
        db,
        client_id=cid,
        upload_root=tmp_path,
        filename="incident_triage.md",
        data=body,
        title="Incident triage",
        source_slack_file_id="FJ11",
        enqueue_ingest=False,
    )
    db.commit()
    # Re-store via Slack helper (idempotent)
    evidence = [
        {
            "client_id": cid,
            "file_id": "FJ11",
            "filename": "incident_triage.md",
            "text": body.decode(),
            "stored_relative_path": seed.template.storage_relative_path,
            "mimetype": "text/markdown",
        }
    ]
    stored = store_workflow_from_slack(
        db=db,
        client_id=cid,
        upload_root=tmp_path,
        attached_evidence=evidence,
        created_by_slack_user_id="U_UPLOADER",
        enqueue_ingest=False,
    )
    assert stored["ok"] is True
    template_id = stored["template"]["id"]
    assert "/app/workflows" in stored["confirmation"]
    assert "copy" in stored["confirmation"].lower()

    listed = list_workflows_for_slack(
        db=db,
        client_id=cid,
        question="list shared workflows",
        slack_user_id="U_COLLEAGUE",
    )
    assert listed["count"] >= 1
    assert any(t["id"] == template_id for t in listed["templates"])

    # Colleague copy — personal draft; original unchanged
    copied = copy_workflow_for_slack(
        db=db,
        client_id=cid,
        upload_root=tmp_path,
        question=f"Copy workflow {template_id}",
        slack_user_id="U_COLLEAGUE",
    )
    assert copied["ok"] is True
    draft_id = copied["template"]["id"]
    assert copied["template"]["visibility"] == "personal"
    assert copied["template"]["parent_id"] == template_id
    original = get_template(db, client_id=cid, template_id=template_id)
    assert original.visibility == "shared"
    assert original.title == "Incident triage"

    # Advice grounded in file (attachment path)
    enriched = enrich_evidence_for_advice(
        db=db,
        client_id=cid,
        question="Advise how we can make this workflow work",
        attached_evidence=evidence,
    )
    assert enriched["ok"] is True

    def search_fn(**_kwargs):
        return KnowledgeSearchResult(hits=[], query="q", client_id=cid)

    advice = run_agent(
        client_id=cid,
        question="Advise how we can make this workflow work based on the attached workflow file",
        conversation_id="j11-smoke",
        settings=Settings(
            agent_checkpointer="memory",
            anthropic_api_key="",
            agent_retrieve_backend="direct",
        ),
        checkpointer=MemorySaver(),
        chat_model=StubChatModel(),
        search_fn=search_fn,
        record_usage=False,
        attached_evidence=enriched["evidence"],
    )
    assert advice["workflow"] == "workflow_advise"
    assert advice["hedge"] is False
    assert advice["answer"]
    assert any(
        "Acknowledge" in (c.get("text") or "") or "triage" in (c.get("text") or "").lower()
        for c in advice["retrieved_chunks"]
    )

    # Advice by stored id (no attachment) still works for the colleague's draft parent
    by_id = enrich_evidence_for_advice(
        db=db,
        client_id=cid,
        question=f"Advise on workflow {template_id}",
        attached_evidence=[],
    )
    assert by_id["ok"] is True
    assert by_id["source"] == "library"
    assert draft_id != template_id

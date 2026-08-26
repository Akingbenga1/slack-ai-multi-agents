"""Workflow library routing + Slack action helpers (Sprint 24.2–24.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.agent.prompts import system_prompt_for
from api.app.db.models import Tenant, WorkflowTemplate
from api.app.slack.workflow_actions import (
    copy_workflow_for_slack,
    enrich_evidence_for_advice,
    extract_copy_template_id,
    list_workflows_for_slack,
    store_workflow_from_slack,
)
from api.app.workflows.library import store_workflow_template


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
    t = Tenant(id=uuid4(), slug=f"r-{uuid4().hex[:8]}", name="R", status="active")
    db.add(t)
    db.commit()
    return t


def test_prompts_exist():
    for wf in (
        "workflow_store",
        "workflow_list",
        "workflow_copy",
        "workflow_edit",
        "workflow_advise",
    ):
        assert system_prompt_for(wf)


def test_store_from_evidence_and_list(db: Session, tenant: Tenant, tmp_path: Path):
    # Seed a stored attachment path like Sprint 23.1
    seed = store_workflow_template(
        db,
        client_id=str(tenant.id),
        upload_root=tmp_path,
        filename="flow.csv",
        data=b"step,note\n1,do it\n",
        title="Seed",
        source_slack_file_id="FSEED",
        enqueue_ingest=False,
    )
    db.commit()
    # Simulate re-store via evidence pointing at same bytes path
    evidence = {
        "client_id": str(tenant.id),
        "file_id": "FSEED",
        "filename": "flow.csv",
        "stored_relative_path": seed.template.storage_relative_path,
        "text": "step,note",
        "mimetype": "text/csv",
    }
    action = store_workflow_from_slack(
        db=db,
        client_id=str(tenant.id),
        upload_root=tmp_path,
        attached_evidence=[evidence],
        created_by_slack_user_id="U1",
        enqueue_ingest=False,
    )
    assert action["ok"] is True
    assert action["created"] is False  # idempotent via file_id/hash

    listed = list_workflows_for_slack(
        db=db,
        client_id=str(tenant.id),
        question="list workflows",
        slack_user_id="U1",
    )
    assert listed["ok"] is True
    assert listed["count"] >= 1
    assert "Shared workflow library" in listed["confirmation"]


def test_copy_by_id_in_question(db: Session, tenant: Tenant, tmp_path: Path):
    stored = store_workflow_template(
        db,
        client_id=str(tenant.id),
        upload_root=tmp_path,
        filename="x.csv",
        data=b"a,b\n",
        title="Shared X",
        enqueue_ingest=False,
    )
    db.commit()
    tid = str(stored.template.id)
    assert extract_copy_template_id(f"Please copy workflow {tid}") == tid

    action = copy_workflow_for_slack(
        db=db,
        client_id=str(tenant.id),
        upload_root=tmp_path,
        question=f"Copy workflow {tid}",
        slack_user_id="U9",
    )
    assert action["ok"] is True
    assert action["template"]["visibility"] == "personal"
    assert action["template"]["parent_id"] == tid


def test_enrich_advice_from_attachment(db: Session, tenant: Tenant):
    evidence = [
        {
            "client_id": str(tenant.id),
            "file_id": "F1",
            "filename": "flow.md",
            "text": "1. Collect\n2. Review\n3. Ship",
            "stored_relative_path": f"{tenant.id}/x_flow.md",
        }
    ]
    out = enrich_evidence_for_advice(
        db=db,
        client_id=str(tenant.id),
        question="Advise how we can make this workflow work",
        attached_evidence=evidence,
    )
    assert out["ok"] is True
    assert out["source"] == "attachment"
    assert "Collect" in out["evidence"][0]["text"]


def test_enrich_advice_from_library_id(
    db: Session, tenant: Tenant, tmp_path: Path
):
    stored = store_workflow_template(
        db,
        client_id=str(tenant.id),
        upload_root=tmp_path,
        filename="ops.md",
        data=b"# Ops\n1. Intake\n2. Approve\n",
        title="Ops Flow",
        enqueue_ingest=False,
    )
    db.commit()
    tid = str(stored.template.id)
    out = enrich_evidence_for_advice(
        db=db,
        client_id=str(tenant.id),
        question=f"Advise on workflow {tid}",
        attached_evidence=[],
    )
    assert out["ok"] is True
    assert out["source"] == "library"
    assert out["template"]["id"] == tid
    assert "Intake" in out["evidence"][0]["text"]


def test_enrich_advice_no_evidence(db: Session, tenant: Tenant):
    out = enrich_evidence_for_advice(
        db=db,
        client_id=str(tenant.id),
        question="Advise how we can make this workflow work",
        attached_evidence=[],
    )
    assert out["ok"] is False
    assert "need the workflow file" in out["confirmation"].lower()


def test_advice_cross_tenant_fail_closed(
    db: Session, tenant: Tenant, tmp_path: Path
):
    other = Tenant(id=uuid4(), slug=f"o-{uuid4().hex[:8]}", name="O", status="active")
    db.add(other)
    db.commit()
    stored = store_workflow_template(
        db,
        client_id=str(tenant.id),
        upload_root=tmp_path,
        filename="secret.md",
        data=b"secret steps",
        title="Secret",
        enqueue_ingest=False,
    )
    db.commit()
    tid = str(stored.template.id)
    out = enrich_evidence_for_advice(
        db=db,
        client_id=str(other.id),
        question=f"Advise on workflow {tid}",
        attached_evidence=[],
    )
    assert out["ok"] is False

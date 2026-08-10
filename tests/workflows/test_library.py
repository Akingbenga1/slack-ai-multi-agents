"""Workflow template library storage (Sprint 24.1–24.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.db.models import Tenant, WorkflowTemplate
from api.app.workflows.library import (
    content_hash_bytes,
    copy_template,
    get_template,
    list_templates,
    require_client_id,
    store_workflow_template,
    update_personal_draft,
)


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
    t = Tenant(id=uuid4(), slug=f"wf-{uuid4().hex[:8]}", name="WF Org", status="active")
    db.add(t)
    db.commit()
    return t


@pytest.fixture
def other_tenant(db: Session) -> Tenant:
    t = Tenant(
        id=uuid4(), slug=f"other-{uuid4().hex[:8]}", name="Other", status="active"
    )
    db.add(t)
    db.commit()
    return t


def test_require_client_id_fail_closed():
    with pytest.raises(ValueError):
        require_client_id("")
    with pytest.raises(ValueError):
        require_client_id(None)


def test_store_and_idempotent(db: Session, tenant: Tenant, tmp_path: Path):
    data = b"Step 1: intake\nStep 2: review\n"
    first = store_workflow_template(
        db,
        client_id=str(tenant.id),
        upload_root=tmp_path,
        filename="onboarding.md",
        data=data,
        title="Onboarding flow",
        source_slack_file_id="F123",
        created_by_slack_user_id="U1",
        enqueue_ingest=False,
    )
    db.commit()
    assert first.created is True
    assert first.template.visibility == "shared"
    assert first.template.content_hash == content_hash_bytes(data)
    stored = tmp_path / first.template.storage_relative_path
    assert stored.is_file()
    assert stored.read_bytes() == data

    second = store_workflow_template(
        db,
        client_id=str(tenant.id),
        upload_root=tmp_path,
        filename="onboarding.md",
        data=data,
        source_slack_file_id="F123",
        enqueue_ingest=False,
    )
    db.commit()
    assert second.created is False
    assert second.template.id == first.template.id


def test_isolation_get_and_list(
    db: Session, tenant: Tenant, other_tenant: Tenant, tmp_path: Path
):
    result = store_workflow_template(
        db,
        client_id=str(tenant.id),
        upload_root=tmp_path,
        filename="a.csv",
        data=b"a,b\n1,2\n",
        title="Alpha",
        enqueue_ingest=False,
    )
    db.commit()
    template_id = result.template.id

    with pytest.raises(LookupError):
        get_template(db, client_id=str(other_tenant.id), template_id=template_id)

    assert list_templates(db, client_id=str(other_tenant.id)) == []
    rows_a = list_templates(db, client_id=str(tenant.id))
    assert len(rows_a) == 1
    assert rows_a[0].title == "Alpha"


def test_copy_and_edit_does_not_mutate_original(
    db: Session, tenant: Tenant, tmp_path: Path
):
    stored = store_workflow_template(
        db,
        client_id=str(tenant.id),
        upload_root=tmp_path,
        filename="proc.csv",
        data=b"step,owner\n1,ops\n",
        title="Shared proc",
        enqueue_ingest=False,
    )
    db.commit()
    original_id = stored.template.id
    original_title = stored.template.title
    original_body = stored.template.body_text

    draft = copy_template(
        db,
        client_id=str(tenant.id),
        upload_root=tmp_path,
        template_id=original_id,
        owner_slack_user_id="U_COPY",
        title="My proc",
    )
    db.commit()
    assert draft.visibility == "personal"
    assert draft.parent_id == original_id
    assert draft.owner_slack_user_id == "U_COPY"
    assert draft.storage_relative_path != stored.template.storage_relative_path

    update_personal_draft(
        db,
        client_id=str(tenant.id),
        template_id=draft.id,
        owner_slack_user_id="U_COPY",
        title="My proc v2",
        body_text="edited body",
    )
    db.commit()

    parent = get_template(db, client_id=str(tenant.id), template_id=original_id)
    assert parent.title == original_title
    assert parent.body_text == original_body
    assert parent.visibility == "shared"

    with pytest.raises(PermissionError):
        update_personal_draft(
            db,
            client_id=str(tenant.id),
            template_id=draft.id,
            owner_slack_user_id="U_OTHER",
            title="hack",
        )


def test_list_includes_personal_for_owner(
    db: Session, tenant: Tenant, tmp_path: Path
):
    shared = store_workflow_template(
        db,
        client_id=str(tenant.id),
        upload_root=tmp_path,
        filename="s.csv",
        data=b"x,y\n",
        title="Shared",
        enqueue_ingest=False,
    )
    db.commit()
    copy_template(
        db,
        client_id=str(tenant.id),
        upload_root=tmp_path,
        template_id=shared.template.id,
        owner_slack_user_id="U_ME",
    )
    db.commit()

    only_shared = list_templates(db, client_id=str(tenant.id))
    assert len(only_shared) == 1
    with_mine = list_templates(
        db, client_id=str(tenant.id), include_personal_for="U_ME"
    )
    assert len(with_mine) == 2
    stranger = list_templates(
        db, client_id=str(tenant.id), include_personal_for="U_OTHER"
    )
    assert len(stranger) == 1

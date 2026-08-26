"""Plan/tool schema tenant isolation (Sprint 41.3)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.db.models import (
    AgentPlan,
    AgentPlanStep,
    AgentRun,
    BillingCustomer,
    McpServer,
    Tenant,
    ToolRegistry,
    WorkflowTemplate,
)
from api.app.db.plan_store import (
    TenantIdRequired,
    decrypt_tool_secret,
    get_agent_plan,
    insert_agent_plan,
    insert_agent_plan_step,
    insert_agent_run,
    insert_mcp_server,
    insert_tool_registry,
    list_agent_plan_steps,
    list_agent_plans,
    list_agent_runs,
    list_mcp_servers,
    list_tool_registry,
    require_tenant_id,
)
from api.app.settings import Settings


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
    McpServer.__table__.create(engine)
    ToolRegistry.__table__.create(engine)
    AgentPlan.__table__.create(engine)
    AgentPlanStep.__table__.create(engine)
    AgentRun.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def tenant_a(db: Session) -> Tenant:
    t = Tenant(id=uuid4(), slug=f"a-{uuid4().hex[:8]}", name="A", status="active")
    db.add(t)
    db.commit()
    return t


@pytest.fixture
def tenant_b(db: Session) -> Tenant:
    t = Tenant(id=uuid4(), slug=f"b-{uuid4().hex[:8]}", name="B", status="active")
    db.add(t)
    db.commit()
    return t


def test_require_tenant_id_fail_closed():
    with pytest.raises(TenantIdRequired):
        require_tenant_id(None)
    with pytest.raises(TenantIdRequired):
        require_tenant_id("")
    with pytest.raises(TenantIdRequired):
        require_tenant_id("  ")


def test_helpers_missing_tenant_id_raise_not_return_all(db: Session, tenant_a: Tenant):
    insert_agent_plan(db, tenant_id=str(tenant_a.id), question="secret")
    db.commit()
    with pytest.raises(TenantIdRequired):
        list_agent_plans(db, tenant_id=None)
    with pytest.raises(TenantIdRequired):
        insert_tool_registry(db, tenant_id="", name="x", kind="mcp")
    with pytest.raises(TenantIdRequired):
        list_tool_registry(db, tenant_id=None)
    with pytest.raises(TenantIdRequired):
        insert_mcp_server(db, tenant_id=None, name="s", transport="http")
    with pytest.raises(TypeError):
        list_agent_plans(db)  # type: ignore[call-arg]


def test_plan_step_tool_isolated_by_tenant(
    db: Session, tenant_a: Tenant, tenant_b: Tenant
):
    settings = Settings(jwt_secret="test-plan-schema-secret")
    server = insert_mcp_server(
        db, tenant_id=str(tenant_a.id), name="local", transport="stdio"
    )
    tool = insert_tool_registry(
        db,
        tenant_id=str(tenant_a.id),
        name="fetch_channel_history",
        kind="mcp",
        mcp_server_id=server.id,
        secret="super-secret",
        settings=settings,
    )
    plan = insert_agent_plan(
        db,
        tenant_id=str(tenant_a.id),
        question="Summarise yesterday in #product",
        source={"channel": "C123", "ts": "1.0"},
    )
    insert_agent_plan_step(
        db,
        tenant_id=str(tenant_a.id),
        plan_id=plan.id,
        step_index=0,
        tool_name="fetch_channel_history",
    )
    insert_agent_run(db, tenant_id=str(tenant_a.id), plan_id=plan.id)
    db.commit()

    assert list_mcp_servers(db, tenant_id=str(tenant_b.id)) == []
    assert list_tool_registry(db, tenant_id=str(tenant_b.id)) == []
    assert list_agent_plans(db, tenant_id=str(tenant_b.id)) == []
    assert get_agent_plan(db, tenant_id=str(tenant_b.id), plan_id=plan.id) is None
    assert list_agent_plan_steps(db, tenant_id=str(tenant_b.id), plan_id=plan.id) == []
    assert list_agent_runs(db, tenant_id=str(tenant_b.id), plan_id=plan.id) == []

    assert [p.id for p in list_agent_plans(db, tenant_id=str(tenant_a.id))] == [plan.id]
    assert get_agent_plan(db, tenant_id=str(tenant_a.id), plan_id=plan.id) is not None
    assert [t.name for t in list_tool_registry(db, tenant_id=str(tenant_a.id))] == [
        "fetch_channel_history"
    ]
    assert tool.secret_encrypted != "super-secret"
    assert decrypt_tool_secret(tool, settings) == "super-secret"
    assert list_agent_plan_steps(db, tenant_id=str(tenant_a.id), plan_id=plan.id)
    assert list_agent_runs(db, tenant_id=str(tenant_a.id), plan_id=plan.id)


def test_library_and_billing_tables_unchanged():
    assert WorkflowTemplate.__tablename__ == "workflow_templates"
    assert "body_text" in WorkflowTemplate.__table__.c
    assert BillingCustomer.__tablename__ == "billing_customers"
    column_names = {c.name for c in ToolRegistry.__table__.columns}
    assert "kind" in column_names
    assert "qa" not in column_names
    assert "meeting_brief" not in column_names
    assert "file_rename" not in column_names

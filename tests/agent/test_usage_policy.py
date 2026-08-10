"""Compose records llm_tokens toward budget (Task 13.3)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.agent.llm import StubChatModel
from api.app.agent.run import run_agent
from api.app.db.models import Tenant, UsageEvent
from api.app.governance.usage import EVENT_LLM_TOKENS
from api.app.retrieval.types import KnowledgeCitation, KnowledgeSearchResult
from api.app.settings import Settings

TENANT = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


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
    UsageEvent.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_compose_records_llm_tokens(db: Session):
    from uuid import UUID

    t = Tenant(id=UUID(TENANT), slug="agent-u", name="A", status="active")
    db.add(t)
    db.commit()

    def search(*, client_id, query, limit=8, settings=None, **_kw):
        return KnowledgeSearchResult(
            client_id=str(client_id),
            query=query,
            hits=[
                KnowledgeCitation(
                    point_id=str(uuid4()),
                    score=0.8,
                    text="evidence text",
                    kind="slack_message",
                    client_id=str(client_id),
                    channel="C1",
                )
            ],
            limit=limit,
        )

    SessionLocal = sessionmaker(bind=db.get_bind())

    def factory() -> Session:
        return SessionLocal()

    settings = Settings(agent_checkpointer="memory", anthropic_api_key="")
    out = run_agent(
        client_id=TENANT,
        question="simple question",
        conversation_id="usage-1",
        settings=settings,
        checkpointer=MemorySaver(),
        search_fn=search,
        chat_model=StubChatModel(),
        db_factory=factory,
        record_usage=True,
    )
    assert out["usage_tokens"] > 0

    rows = db.scalars(
        select(UsageEvent).where(UsageEvent.event_type == EVENT_LLM_TOKENS)
    ).all()
    # factory opens a different session; refresh via new query on same engine
    db.expire_all()
    rows = list(
        db.scalars(select(UsageEvent).where(UsageEvent.tenant_id == t.id)).all()
    )
    assert len(rows) == 1
    assert rows[0].event_type == EVENT_LLM_TOKENS
    assert rows[0].units == out["usage_tokens"]
    assert rows[0].meta.get("model_tier") == "haiku"

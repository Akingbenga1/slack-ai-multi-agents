"""Dry-run / invoke helpers for the offline agent (Sprint 13)."""

from __future__ import annotations

from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.orm import Session

from api.app.agent.checkpointer import get_checkpointer, thread_id_for_tenant
from api.app.agent.graph import build_agent_graph, build_report_graph
from api.app.agent.llm import ChatModel, get_chat_model, message_content
from api.app.agent.mcp_client import McpCallTool
from api.app.agent.nodes.retrieve import SearchFn
from api.app.db.session import SessionLocal
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings

logger = get_logger("api.agent.run")

DEFAULT_REPORT_WINDOW = "last 7 days"


def _default_db_factory() -> Session:
    return SessionLocal()


def run_agent(
    *,
    client_id: str,
    question: str,
    conversation_id: str | None = None,
    settings: Settings | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    search_fn: Optional[SearchFn] = None,
    mcp_call_tool: Optional[McpCallTool] = None,
    chat_model: Optional[ChatModel] = None,
    db_factory: Optional[Callable[[], Session]] = None,
    record_usage: bool = True,
    system_prompt: str | None = None,
    attached_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Invoke route → tools (MCP) → compose for one tenant.

    Does not post to Slack — callers (dry-run, Slack `process_agent_reply`)
    own delivery. Returns answer, workflow, model_tier, retrieved_chunks,
    usage_tokens, thread_id, hedge. Optional ``attached_evidence`` carries
    Slack attachment text (Sprint 23) into graph state.
    """
    settings = settings or get_settings()
    cid = str(UUID(str(client_id).strip()))
    q = (question or "").strip()
    if not q:
        raise ValueError("question must be non-empty")

    saver = checkpointer if checkpointer is not None else get_checkpointer(settings)
    model = chat_model if chat_model is not None else get_chat_model(settings)
    factory = db_factory if record_usage else None
    if record_usage and factory is None:
        factory = _default_db_factory

    org_prompt: str | None = None
    if system_prompt is None:
        prompt_db = _default_db_factory()
        try:
            from api.app.agent.config_store import load_org_system_prompt

            org_prompt = load_org_system_prompt(prompt_db, cid)
        except Exception:
            logger.exception("org_system_prompt_load_failed client_id=%s", cid)
        finally:
            prompt_db.close()

    graph = build_agent_graph(
        settings=settings,
        checkpointer=saver,
        search_fn=search_fn,
        mcp_call_tool=mcp_call_tool,
        chat_model=model,
        db_factory=factory,
        system_prompt=system_prompt,
    )

    thread_id = thread_id_for_tenant(cid, conversation_id or str(uuid4()))
    config = {"configurable": {"thread_id": thread_id}}
    attachments = list(attached_evidence or [])
    # Drop foreign-tenant attachment payloads (fail-closed isolation)
    attachments = [
        a
        for a in attachments
        if isinstance(a, dict) and (a.get("client_id") or "").strip() == cid
    ]
    initial: dict[str, Any] = {
        "client_id": cid,
        "messages": [HumanMessage(content=q)],
        "question": q,
        "retrieved_chunks": [],
        "workflow": "qa",
        "model_tier": "haiku",
        "complexity_flags": [],
        "attached_evidence": attachments,
    }
    if org_prompt:
        initial["org_system_prompt"] = org_prompt
    final = graph.invoke(initial, config)

    answer = final.get("answer") or ""
    if not answer:
        # Fallback: last AI message content
        for msg in reversed(final.get("messages") or []):
            role = getattr(msg, "type", None)
            if role == "ai":
                answer = message_content(msg)
                break

    logger.info(
        "agent_run_ok client_id=%s thread_id=%s workflow=%s tier=%s chunks=%s attachments=%s",
        cid,
        thread_id,
        final.get("workflow"),
        final.get("model_tier"),
        len(final.get("retrieved_chunks") or []),
        len(attachments),
    )
    return {
        "client_id": cid,
        "thread_id": thread_id,
        "question": q,
        "answer": answer,
        "workflow": final.get("workflow"),
        "model_tier": final.get("model_tier"),
        "complexity_flags": list(final.get("complexity_flags") or []),
        "retrieved_chunks": list(final.get("retrieved_chunks") or []),
        "usage_tokens": int(final.get("usage_tokens") or 0),
        "hedge": bool(final.get("hedge")),
        "meeting_draft": str(final.get("meeting_draft") or ""),
        "report_window": str(final.get("report_window") or ""),
        "attached_evidence": list(final.get("attached_evidence") or attachments),
    }


def run_report(
    *,
    client_id: str,
    window_label: str = DEFAULT_REPORT_WINDOW,
    channel: str | None = None,
    topic: str | None = None,
    conversation_id: str | None = None,
    settings: Settings | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    search_fn: Optional[SearchFn] = None,
    mcp_call_tool: Optional[McpCallTool] = None,
    chat_model: Optional[ChatModel] = None,
    db_factory: Optional[Callable[[], Session]] = None,
    record_usage: bool = True,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """
    Invoke the report subgraph (tools → compose) for one tenant.

    Forces ``workflow=report`` and Sonnet escalation. Does not post to Slack —
    Celery Beat (Sprint 17.3) will own delivery. ``window_label`` describes the
    digest window (e.g. ``last 7 days``); optional ``channel`` scopes retrieval.
    """
    settings = settings or get_settings()
    cid = str(UUID(str(client_id).strip()))
    window = (window_label or "").strip() or DEFAULT_REPORT_WINDOW
    chan = (channel or "").strip() or None
    subject = (topic or "").strip() or f"Recurring report for {window}"
    if chan:
        subject = f"{subject} (channel {chan})"

    saver = checkpointer if checkpointer is not None else get_checkpointer(settings)
    model = chat_model if chat_model is not None else get_chat_model(settings)
    factory = db_factory if record_usage else None
    if record_usage and factory is None:
        factory = _default_db_factory

    graph = build_report_graph(
        settings=settings,
        checkpointer=saver,
        search_fn=search_fn,
        mcp_call_tool=mcp_call_tool,
        chat_model=model,
        db_factory=factory,
        system_prompt=system_prompt,
    )

    thread_id = thread_id_for_tenant(
        cid, conversation_id or f"report:{chan or 'workspace'}:{window}"
    )
    config = {"configurable": {"thread_id": thread_id}}
    initial: dict[str, Any] = {
        "client_id": cid,
        "messages": [HumanMessage(content=subject)],
        "question": subject,
        "retrieved_chunks": [],
        "workflow": "report",
        "model_tier": "sonnet",
        "complexity_flags": ["workflow:report"],
        "report_window": window,
        "report_channel": chan or "",
        "meeting_draft": "",
    }
    final = graph.invoke(initial, config)

    answer = final.get("answer") or ""
    if not answer:
        for msg in reversed(final.get("messages") or []):
            role = getattr(msg, "type", None)
            if role == "ai":
                answer = message_content(msg)
                break

    logger.info(
        "agent_report_ok client_id=%s thread_id=%s window=%s channel=%s chunks=%s",
        cid,
        thread_id,
        window,
        chan,
        len(final.get("retrieved_chunks") or []),
    )
    return {
        "client_id": cid,
        "thread_id": thread_id,
        "question": subject,
        "answer": answer,
        "workflow": "report",
        "model_tier": final.get("model_tier") or "sonnet",
        "complexity_flags": list(final.get("complexity_flags") or ["workflow:report"]),
        "retrieved_chunks": list(final.get("retrieved_chunks") or []),
        "usage_tokens": int(final.get("usage_tokens") or 0),
        "hedge": bool(final.get("hedge")),
        "meeting_draft": str(final.get("meeting_draft") or ""),
        "report_window": str(final.get("report_window") or window),
        "report_channel": chan or "",
    }

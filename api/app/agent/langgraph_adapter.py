"""LangGraph Adapter for ``AgentRuntime`` (Sprint 39).

Owns ``StateGraph`` compile + checkpointer invoke. Product nodes (route /
tools / compose / trim) and ``AgentRuntimeDeps`` stay injectable; Slack /
billing / DeliveryStrategy never import this module.
"""

from __future__ import annotations

from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from api.app.agent.checkpointer import get_checkpointer, thread_id_for_tenant
from api.app.agent.deps import AgentRuntimeDeps, build_agent_deps
from api.app.agent.llm import ChatModel, get_chat_model, message_content
from api.app.agent.mcp_client import McpCallTool
from api.app.agent.nodes.compose import make_compose_node
from api.app.agent.nodes.retrieve import SearchFn
from api.app.agent.nodes.route import route_node
from api.app.agent.nodes.tools import make_tools_node
from api.app.agent.nodes.trim import make_trim_messages_node
from api.app.agent.state import AgentState
from api.app.db.session import SessionLocal
from api.app.logging_config import get_logger
from api.app.settings import Settings

logger = get_logger("api.agent.langgraph_adapter")

DEFAULT_REPORT_WINDOW = "last 7 days"


def _default_db_factory() -> Session:
    return SessionLocal()


def build_agent_graph(
    deps: AgentRuntimeDeps | None = None,
    *,
    settings: Settings | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    search_fn: Optional[SearchFn] = None,
    mcp_call_tool: Optional[McpCallTool] = None,
    chat_model: Optional[ChatModel] = None,
    db_factory: Optional[Callable[[], Session]] = None,
    system_prompt: str | None = None,
    top_k: int | None = None,
):
    """
    Build and compile the core agent StateGraph (LangGraph adapter internal).

    Nodes: route → tools → compose → trim.
    Prefer ``deps=AgentRuntimeDeps(...)``; kwargs override or stand alone.
    """
    resolved = build_agent_deps(
        deps,
        settings=settings,
        checkpointer=checkpointer,
        search_fn=search_fn,
        mcp_call_tool=mcp_call_tool,
        chat_model=chat_model,
        db_factory=db_factory,
        system_prompt=system_prompt,
        top_k=top_k,
    )
    tools = make_tools_node(
        settings=resolved.settings,
        search_fn=resolved.search_fn,
        mcp_call_tool=resolved.mcp_call_tool,
        top_k=resolved.top_k,
    )
    compose = make_compose_node(
        settings=resolved.settings,
        chat_model=resolved.chat_model,
        db_factory=resolved.db_factory,
        system_prompt=resolved.system_prompt,
    )
    trim = make_trim_messages_node(settings=resolved.settings)

    graph = StateGraph(AgentState)
    graph.add_node("route", route_node)
    graph.add_node("tools", tools)
    graph.add_node("compose", compose)
    graph.add_node("trim", trim)
    graph.add_edge(START, "route")
    graph.add_edge("route", "tools")
    graph.add_edge("tools", "compose")
    graph.add_edge("compose", "trim")
    graph.add_edge("trim", END)

    kwargs: dict[str, Any] = {}
    if resolved.checkpointer is not None:
        kwargs["checkpointer"] = resolved.checkpointer
    return graph.compile(**kwargs)


def build_report_graph(
    deps: AgentRuntimeDeps | None = None,
    *,
    settings: Settings | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    search_fn: Optional[SearchFn] = None,
    mcp_call_tool: Optional[McpCallTool] = None,
    chat_model: Optional[ChatModel] = None,
    db_factory: Optional[Callable[[], Session]] = None,
    system_prompt: str | None = None,
    top_k: int | None = None,
):
    """
    Report StateGraph for scheduled digests (adapter internal).

    Nodes: tools → compose → trim (no route — caller forces ``workflow=report``).
    """
    resolved = build_agent_deps(
        deps,
        settings=settings,
        checkpointer=checkpointer,
        search_fn=search_fn,
        mcp_call_tool=mcp_call_tool,
        chat_model=chat_model,
        db_factory=db_factory,
        system_prompt=system_prompt,
        top_k=top_k,
    )
    tools = make_tools_node(
        settings=resolved.settings,
        search_fn=resolved.search_fn,
        mcp_call_tool=resolved.mcp_call_tool,
        top_k=resolved.top_k,
    )
    compose = make_compose_node(
        settings=resolved.settings,
        chat_model=resolved.chat_model,
        db_factory=resolved.db_factory,
        system_prompt=resolved.system_prompt,
    )
    trim = make_trim_messages_node(settings=resolved.settings)

    graph = StateGraph(AgentState)
    graph.add_node("tools", tools)
    graph.add_node("compose", compose)
    graph.add_node("trim", trim)
    graph.add_edge(START, "tools")
    graph.add_edge("tools", "compose")
    graph.add_edge("compose", "trim")
    graph.add_edge("trim", END)

    kwargs: dict[str, Any] = {}
    if resolved.checkpointer is not None:
        kwargs["checkpointer"] = resolved.checkpointer
    return graph.compile(**kwargs)


def _answer_from_final(final: dict[str, Any]) -> str:
    answer = final.get("answer") or ""
    if answer:
        return answer
    for msg in reversed(final.get("messages") or []):
        role = getattr(msg, "type", None)
        if role == "ai":
            return message_content(msg)
    return ""


class LangGraphAgentRuntime:
    """LangGraph StateGraph + checkpointer adapter."""

    name = "langgraph"

    def run(
        self,
        *,
        client_id: str,
        question: str,
        conversation_id: str | None = None,
        deps: AgentRuntimeDeps | None = None,
        record_usage: bool = True,
        attached_evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        resolved = build_agent_deps(deps)
        settings = resolved.settings
        cid = str(UUID(str(client_id).strip()))
        q = (question or "").strip()
        if not q:
            raise ValueError("question must be non-empty")

        saver = (
            resolved.checkpointer
            if resolved.checkpointer is not None
            else get_checkpointer(settings)
        )
        model = (
            resolved.chat_model
            if resolved.chat_model is not None
            else get_chat_model(settings)
        )
        factory = resolved.db_factory if record_usage else None
        if record_usage and factory is None:
            factory = _default_db_factory

        org_prompt: str | None = None
        prompt_override = resolved.system_prompt
        if prompt_override is None:
            prompt_db = _default_db_factory()
            try:
                from api.app.agent.config_store import load_org_system_prompt

                org_prompt = load_org_system_prompt(prompt_db, cid)
            except Exception:
                logger.exception("org_system_prompt_load_failed client_id=%s", cid)
            finally:
                prompt_db.close()

        graph = build_agent_graph(
            deps=AgentRuntimeDeps(
                settings=settings,
                checkpointer=saver,
                search_fn=resolved.search_fn,
                mcp_call_tool=resolved.mcp_call_tool,
                chat_model=model,
                db_factory=factory,
                system_prompt=prompt_override,
                top_k=resolved.top_k,
            )
        )

        thread_id = thread_id_for_tenant(cid, conversation_id or str(uuid4()))
        config = {"configurable": {"thread_id": thread_id}}
        attachments = list(attached_evidence or [])
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
            "model_tier": "fast",
            "complexity_flags": [],
            "attached_evidence": attachments,
        }
        if org_prompt:
            initial["org_system_prompt"] = org_prompt
        final = graph.invoke(initial, config)

        answer = _answer_from_final(final)
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
        self,
        *,
        client_id: str,
        window_label: str = DEFAULT_REPORT_WINDOW,
        channel: str | None = None,
        topic: str | None = None,
        conversation_id: str | None = None,
        deps: AgentRuntimeDeps | None = None,
        record_usage: bool = True,
    ) -> dict[str, Any]:
        resolved = build_agent_deps(deps)
        settings = resolved.settings
        cid = str(UUID(str(client_id).strip()))
        window = (window_label or "").strip() or DEFAULT_REPORT_WINDOW
        chan = (channel or "").strip() or None
        subject = (topic or "").strip() or f"Recurring report for {window}"
        if chan:
            subject = f"{subject} (channel {chan})"

        saver = (
            resolved.checkpointer
            if resolved.checkpointer is not None
            else get_checkpointer(settings)
        )
        model = (
            resolved.chat_model
            if resolved.chat_model is not None
            else get_chat_model(settings)
        )
        factory = resolved.db_factory if record_usage else None
        if record_usage and factory is None:
            factory = _default_db_factory

        graph = build_report_graph(
            deps=AgentRuntimeDeps(
                settings=settings,
                checkpointer=saver,
                search_fn=resolved.search_fn,
                mcp_call_tool=resolved.mcp_call_tool,
                chat_model=model,
                db_factory=factory,
                system_prompt=resolved.system_prompt,
                top_k=resolved.top_k,
            )
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
            "model_tier": "capable",
            "complexity_flags": ["workflow:report"],
            "report_window": window,
            "report_channel": chan or "",
            "meeting_draft": "",
        }
        final = graph.invoke(initial, config)

        answer = _answer_from_final(final)
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
            "model_tier": final.get("model_tier") or "capable",
            "complexity_flags": list(
                final.get("complexity_flags") or ["workflow:report"]
            ),
            "retrieved_chunks": list(final.get("retrieved_chunks") or []),
            "usage_tokens": int(final.get("usage_tokens") or 0),
            "hedge": bool(final.get("hedge")),
            "meeting_draft": str(final.get("meeting_draft") or ""),
            "report_window": str(final.get("report_window") or window),
            "report_channel": chan or "",
        }

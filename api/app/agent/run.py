"""Dry-run / invoke helpers for the offline agent (Sprint 13 / 39).

Product facade: ``run_agent`` / ``run_report`` → ``AgentRuntime``. LangGraph
lives in ``langgraph_adapter``. Prefer ``deps=AgentRuntimeDeps(...)``; individual
kwargs remain for back-compat with tests, Slack injects, and CLI scripts.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.orm import Session

from api.app.agent.deps import AgentRuntimeDeps, build_agent_deps
from api.app.agent.llm import ChatModel
from api.app.agent.mcp_client import McpCallTool
from api.app.agent.nodes.retrieve import SearchFn
from api.app.agent.runtime import AgentRuntime, default_agent_runtime
from api.app.settings import Settings

DEFAULT_REPORT_WINDOW = "last 7 days"


def run_agent(
    *,
    client_id: str,
    question: str,
    conversation_id: str | None = None,
    deps: AgentRuntimeDeps | None = None,
    settings: Settings | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    search_fn: Optional[SearchFn] = None,
    mcp_call_tool: Optional[McpCallTool] = None,
    chat_model: Optional[ChatModel] = None,
    db_factory: Optional[Callable[[], Session]] = None,
    record_usage: bool = True,
    system_prompt: str | None = None,
    attached_evidence: list[dict[str, Any]] | None = None,
    runtime: AgentRuntime | None = None,
) -> dict[str, Any]:
    """
    Invoke route → tools (MCP) → compose for one tenant.

    Does not post to Slack — callers (dry-run, Slack `process_agent_reply`)
    own delivery. Returns answer, workflow, model_tier, retrieved_chunks,
    usage_tokens, thread_id, hedge. Optional ``attached_evidence`` carries
    Slack attachment text (Sprint 23) into graph state.

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
    )
    rt = runtime or default_agent_runtime()
    return rt.run(
        client_id=client_id,
        question=question,
        conversation_id=conversation_id,
        deps=resolved,
        record_usage=record_usage,
        attached_evidence=attached_evidence,
    )


def run_report(
    *,
    client_id: str,
    window_label: str = DEFAULT_REPORT_WINDOW,
    channel: str | None = None,
    topic: str | None = None,
    conversation_id: str | None = None,
    deps: AgentRuntimeDeps | None = None,
    settings: Settings | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    search_fn: Optional[SearchFn] = None,
    mcp_call_tool: Optional[McpCallTool] = None,
    chat_model: Optional[ChatModel] = None,
    db_factory: Optional[Callable[[], Session]] = None,
    record_usage: bool = True,
    system_prompt: str | None = None,
    runtime: AgentRuntime | None = None,
) -> dict[str, Any]:
    """
    Invoke the report subgraph (tools → compose) for one tenant.

    Forces ``workflow=report`` and capable-tier escalation. Does not post to Slack —
    Celery Beat (Sprint 17.3) will own delivery. ``window_label`` describes the
    digest window (e.g. ``last 7 days``); optional ``channel`` scopes retrieval.

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
    )
    rt = runtime or default_agent_runtime()
    return rt.run_report(
        client_id=client_id,
        window_label=window_label,
        channel=channel,
        topic=topic,
        conversation_id=conversation_id,
        deps=resolved,
        record_usage=record_usage,
    )

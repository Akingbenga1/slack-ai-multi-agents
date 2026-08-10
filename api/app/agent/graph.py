"""Compile the LangGraph agent: route → tools (MCP) → compose.

Also exposes a report subgraph (tools → compose) for scheduled digests.

Prefer passing an ``AgentRuntimeDeps`` bag (Sprint 25.1); individual kwargs
remain for back-compat with tests and scripts.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from api.app.agent.deps import AgentRuntimeDeps, build_agent_deps
from api.app.agent.llm import ChatModel
from api.app.agent.mcp_client import McpCallTool
from api.app.agent.nodes.compose import make_compose_node
from api.app.agent.nodes.retrieve import SearchFn
from api.app.agent.nodes.route import route_node
from api.app.agent.nodes.tools import make_tools_node
from api.app.agent.state import AgentState
from api.app.settings import Settings


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
    Build and compile the core agent graph.

    Nodes: route → tools → compose.
    The tools node calls bundled MCP ``search_knowledge`` by default
    (inject ``search_fn`` / ``mcp_call_tool`` in tests).
    Pass a checkpointer for thread continuity (Sprint 13.2).
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

    graph = StateGraph(AgentState)
    graph.add_node("route", route_node)
    graph.add_node("tools", tools)
    graph.add_node("compose", compose)
    graph.add_edge(START, "route")
    graph.add_edge("route", "tools")
    graph.add_edge("tools", "compose")
    graph.add_edge("compose", END)

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
    Report subgraph for scheduled digests (Sprint 17.1).

    Nodes: tools → compose (no route — caller forces ``workflow=report``).
    Ready for Celery Beat (17.3) to invoke via ``run_report``.
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

    graph = StateGraph(AgentState)
    graph.add_node("tools", tools)
    graph.add_node("compose", compose)
    graph.add_edge(START, "tools")
    graph.add_edge("tools", "compose")
    graph.add_edge("compose", END)

    kwargs: dict[str, Any] = {}
    if resolved.checkpointer is not None:
        kwargs["checkpointer"] = resolved.checkpointer
    return graph.compile(**kwargs)

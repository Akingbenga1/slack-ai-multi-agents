"""Agent runtime dependency bag (Sprint 25.1 — Factory for Strategy injection).

Bundles settings + injectables so ``AgentRuntime`` / ``run_agent`` /
Slack reply take one deps object instead of repeating keyword knobs.
LangGraph checkpointer types stay here; ``AGENT_CHECKPOINTER`` is not a vendor Strategy.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.orm import Session

from api.app.agent.llm import ChatModel
from api.app.agent.mcp_client import McpCallTool
from api.app.agent.nodes.retrieve import SearchFn
from api.app.settings import Settings, get_settings


@dataclass(frozen=True)
class AgentRuntimeDeps:
    """Injectables for the LangGraph agent (graph compile + invoke).

    Factory builds one instance per request/tenant (or test). Strategy nodes
    (tools / compose / later delivery) read from this bag — no ambient globals
    beyond existing request-scoped ContextVar usage.
    """

    settings: Settings
    checkpointer: BaseCheckpointSaver | None = None
    search_fn: Optional[SearchFn] = None
    mcp_call_tool: Optional[McpCallTool] = None
    chat_model: Optional[ChatModel] = None
    db_factory: Optional[Callable[[], Session]] = None
    system_prompt: str | None = None
    top_k: int | None = None


def build_agent_deps(
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
) -> AgentRuntimeDeps:
    """
    Merge an optional deps object with per-call overrides.

    Omitted overrides keep the base deps value. When ``deps`` is None, builds
    a fresh bag (settings default to ``get_settings()``).
    """
    if deps is None:
        return AgentRuntimeDeps(
            settings=settings or get_settings(),
            checkpointer=checkpointer,
            search_fn=search_fn,
            mcp_call_tool=mcp_call_tool,
            chat_model=chat_model,
            db_factory=db_factory,
            system_prompt=system_prompt,
            top_k=top_k,
        )

    updates: dict[str, object] = {}
    if settings is not None:
        updates["settings"] = settings
    if checkpointer is not None:
        updates["checkpointer"] = checkpointer
    if search_fn is not None:
        updates["search_fn"] = search_fn
    if mcp_call_tool is not None:
        updates["mcp_call_tool"] = mcp_call_tool
    if chat_model is not None:
        updates["chat_model"] = chat_model
    if db_factory is not None:
        updates["db_factory"] = db_factory
    if system_prompt is not None:
        updates["system_prompt"] = system_prompt
    if top_k is not None:
        updates["top_k"] = top_k
    return replace(deps, **updates) if updates else deps

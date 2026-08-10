"""LangGraph tool node — dispatch via ToolStrategy map (Sprint 25.4)."""

from __future__ import annotations

from typing import Any, Callable, Optional

from api.app.agent.guardrails import require_tenant_client_id
from api.app.agent.mcp_client import McpCallTool
from api.app.agent.nodes.retrieve import SearchFn
from api.app.agent.state import AgentState
from api.app.agent.workflows.tool_strategies import (
    empty_question_result,
    get_tool_strategy,
    resolve_tools_context,
)
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings

logger = get_logger("api.agent.nodes.tools")


def make_tools_node(
    *,
    settings: Settings | None = None,
    search_fn: Optional[SearchFn] = None,
    mcp_call_tool: Optional[McpCallTool] = None,
    top_k: int | None = None,
) -> Callable[[AgentState], dict[str, Any]]:
    """
    Build the agent tool node.

    Resolves inject / direct / MCP search once, then runs
    ``get_tool_strategy(workflow).run(...)``. Inject ``search_fn`` to skip
    MCP (unit tests), or ``mcp_call_tool`` to stub the MCP transport.
    """
    settings = settings or get_settings()
    ctx = resolve_tools_context(
        settings=settings,
        search_fn=search_fn,
        mcp_call_tool=mcp_call_tool,
        top_k=top_k,
    )

    def tools_node(state: AgentState) -> dict[str, Any]:
        client_id = require_tenant_client_id(
            state.get("client_id"),
            where="tools",
        )

        question = (state.get("question") or "").strip()
        if not question:
            logger.info(
                "agent_tools skip empty question client_id=%s via=%s",
                client_id,
                ctx.via,
            )
            return empty_question_result(client_id)

        workflow = state.get("workflow") or "qa"
        return get_tool_strategy(workflow).run(state, ctx)

    return tools_node

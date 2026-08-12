"""Agent-runtime Adapter contract (Sprint 39).

Product code asks for ``run`` / ``run_report`` on a tenant thread. LangGraph
(StateGraph + checkpointer) lives in the first adapter. No Factory / env key
this sprint — add ``AGENT_RUNTIME`` only when a second runtime is selected.
"""

from __future__ import annotations

from typing import Any, Protocol

from api.app.agent.deps import AgentRuntimeDeps


class AgentRuntime(Protocol):
    """Vendor-neutral agent invoke (thread-scoped)."""

    @property
    def name(self) -> str:
        """Adapter id (e.g. ``langgraph``)."""
        ...

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
        """Invoke the main agent path for one tenant; return product result dict."""
        ...

    def run_report(
        self,
        *,
        client_id: str,
        window_label: str = "last 7 days",
        channel: str | None = None,
        topic: str | None = None,
        conversation_id: str | None = None,
        deps: AgentRuntimeDeps | None = None,
        record_usage: bool = True,
    ) -> dict[str, Any]:
        """Invoke the report path for one tenant; return product result dict."""
        ...


def default_agent_runtime() -> AgentRuntime:
    """Composition root for the single LangGraph product — not an env Factory.

    Add ``AGENT_RUNTIME`` + ``get_agent_runtime(settings)`` only when a second
    backend is env-selected.
    """
    from api.app.agent.langgraph_adapter import LangGraphAgentRuntime

    return LangGraphAgentRuntime()

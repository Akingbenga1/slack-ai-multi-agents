"""Agent role Factory Method (Sprint 42).

Product code asks for ``get_agent("orchestrator")`` / ``get_agent("executor")``.
Concrete classes are registered here only — Slack and ``run.py`` must not
import them. This is not ``AGENT_RUNTIME`` (Sprint 39 vendor adapter).
"""

from __future__ import annotations

from typing import Callable

from api.app.agent.base import Agent

AgentBuilder = Callable[[], Agent]

_REGISTRY: dict[str, AgentBuilder] | None = None


def _default_registry() -> dict[str, AgentBuilder]:
    from api.app.agent.executor import ExecutorAgent
    from api.app.agent.orchestrator import OrchestratorAgent

    return {
        "orchestrator": OrchestratorAgent,
        "executor": ExecutorAgent,
    }


def _registry() -> dict[str, AgentBuilder]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _default_registry()
    return _REGISTRY


def get_agent(role: str) -> Agent:
    """Factory: return an Agent implementation for ``role``."""
    key = (role or "").strip().lower()
    builder = _registry().get(key)
    if builder is None:
        known = ", ".join(sorted(_registry()))
        raise ValueError(
            f"Unknown agent role {role!r}; expected one of: {known}"
        )
    return builder()

"""Product Agent contract (Sprint 42).

One small ABC: ``role`` + ``run(context)``. Template Method owns tenant id,
structured logging, and an optional usage hook. Orchestrator and Executor
differ inside ``_run_impl`` — this is not a fat ``plan()`` + ``execute()``
interface and not a composite tree of child agents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from api.app.agent.guardrails import require_tenant_client_id
from api.app.logging_config import get_logger

logger = get_logger("api.agent.base")

UsageHook = Callable[["AgentContext", "AgentResult"], None]

# Current Agent.role for LLM prompt logging (orchestrator / executor).
current_agent_role: ContextVar[str | None] = ContextVar(
    "current_agent_role", default=None
)


@dataclass
class AgentContext:
    """Input to ``Agent.run``. Product callers pass tenant + question."""

    client_id: str
    question: str = ""
    conversation_id: str | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    record_usage: bool = False
    usage_hook: Optional[UsageHook] = None


@dataclass
class AgentResult:
    """Output of ``Agent.run``. Role-specific details stay in ``extra``."""

    role: str
    client_id: str
    status: str
    message: str
    extra: dict[str, Any] = field(default_factory=dict)


class Agent(ABC):
    """Planner or runner (or a later role). Not a vendor ``AgentRuntime``."""

    @property
    @abstractmethod
    def role(self) -> str:
        """Registry key, e.g. ``orchestrator`` or ``executor``."""

    def run(self, context: AgentContext) -> AgentResult:
        """Template Method: require tenant → log → role work → optional usage."""
        client_id = require_tenant_client_id(
            context.client_id,
            where=f"agent.{self.role}",
        )
        role_token = current_agent_role.set(self.role)
        logger.info("agent_run_start role=%s client_id=%s", self.role, client_id)
        try:
            result = self._run_impl(context)
        finally:
            current_agent_role.reset(role_token)
        logger.info(
            "agent_run_finish role=%s client_id=%s status=%s",
            self.role,
            client_id,
            result.status,
        )
        if context.record_usage and context.usage_hook is not None:
            context.usage_hook(context, result)
        return result

    @abstractmethod
    def _run_impl(self, context: AgentContext) -> AgentResult:
        """Role-specific work. Base class does not plan, execute tools, or post."""

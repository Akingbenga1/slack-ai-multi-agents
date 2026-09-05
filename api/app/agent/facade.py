"""Plan-and-execute facade.

Single entry point: ``plan_and_execute``. Callers pass tenant + question;
the facade runs the Deep Agents harness (no Slack posting, no delivery —
workspace promotion + verification only).
"""

from __future__ import annotations

from typing import Any

from api.app.agent.base import AgentResult
from api.app.agent.harness import run_deep_agent
from api.app.logging_config import get_logger

logger = get_logger("api.agent.facade")


def plan_and_execute(
    *,
    client_id: str,
    question: str,
    conversation_id: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> AgentResult:
    """Run the Deep Agents harness for this tenant request."""
    extra = dict(extra or {})
    logger.info("facade_start client_id=%s", client_id)
    result = run_deep_agent(
        client_id=client_id,
        question=question,
        conversation_id=conversation_id,
        attachments=attachments,
        extra=extra,
    )
    logger.info(
        "facade_harness_done client_id=%s status=%s plan_id=%s",
        client_id,
        result.status,
        result.extra.get("plan_id"),
    )
    return result

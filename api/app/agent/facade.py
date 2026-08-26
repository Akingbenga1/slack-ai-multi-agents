"""Plan-and-execute facade (Sprint 46).

Single entry point: ``plan_and_execute``. Callers pass tenant + question;
the facade obtains the orchestrator and executor via the factory and
chains them. No Slack posting, no delivery — pure plan then run.
"""

from __future__ import annotations

from typing import Any

from api.app.agent.base import AgentContext, AgentResult
from api.app.agent.factory import get_agent
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
    """Orchestrate then execute. Returns the executor result on success."""
    extra = dict(extra or {})
    logger.info("facade_start client_id=%s", client_id)

    orchestrator = get_agent("orchestrator")
    orch_ctx = AgentContext(
        client_id=client_id,
        question=question,
        conversation_id=conversation_id,
        attachments=list(attachments or []),
        extra=extra,
    )
    orch_result = orchestrator.run(orch_ctx)
    logger.info(
        "facade_orchestrator_done client_id=%s status=%s plan_id=%s",
        client_id,
        orch_result.status,
        orch_result.extra.get("plan_id"),
    )

    workflow = orch_result.extra.get("workflow") or "qa"
    include_trace = bool(extra.get("include_trace"))
    trace_keys = (
        "orchestrator_system_prompt",
        "orchestrator_user_prompt",
        "plan_steps",
        "planner_raw",
        "planner_model",
        "planner_model_tier",
        "safety_violations",
    )

    def _trace_from_orch() -> dict[str, Any]:
        if not include_trace:
            return {}
        return {
            key: orch_result.extra[key]
            for key in trace_keys
            if key in orch_result.extra
        }

    if orch_result.status != "ready":
        return AgentResult(
            role="facade",
            client_id=client_id,
            status="failed",
            message=orch_result.message,
            extra={
                "plan_id": orch_result.extra.get("plan_id"),
                "phase": "orchestrator",
                "workflow": workflow,
                **_trace_from_orch(),
            },
        )

    plan_id = orch_result.extra["plan_id"]
    exec_extra = dict(extra)
    exec_extra["plan_id"] = plan_id

    executor = get_agent("executor")
    exec_ctx = AgentContext(
        client_id=client_id,
        question=question,
        conversation_id=conversation_id,
        attachments=list(attachments or []),
        extra=exec_extra,
    )
    exec_result = executor.run(exec_ctx)
    logger.info(
        "facade_executor_done client_id=%s status=%s run_id=%s",
        client_id,
        exec_result.status,
        exec_result.extra.get("run_id"),
    )

    return AgentResult(
        role="facade",
        client_id=client_id,
        status=exec_result.status,
        message=exec_result.message,
        extra={
            "plan_id": plan_id,
            "run_id": exec_result.extra.get("run_id"),
            "phase": "executor",
            "workflow": workflow,
            **_trace_from_orch(),
        },
    )

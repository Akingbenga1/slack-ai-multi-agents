"""Executor Agent (Sprint 48). Sequential plan execution with tool calling.

Loads a persisted plan and runs steps one at a time in order. Before each
step, preconditions are checked against runtime context (attachments, etc.).
Advice and halt steps produce user-facing output; halt and failed
preconditions stop the run without executing later steps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from api.app.agent.base import Agent, AgentContext, AgentResult
from api.app.agent.llm import ChatModel, get_chat_model
from api.app.agent.plan_steps import (
    STEP_TYPE_ADVICE,
    STEP_TYPE_HALT,
    STEP_TYPE_TOOL,
    ExecutionContext,
    check_preconditions,
    infer_step_type,
    precondition_fail_message,
    step_message,
    step_meta,
    tool_arguments,
)
from api.app.agent.tools import (
    DbToolDiscovery,
    ToolDiscovery,
    ToolExecutionError,
    invoke_tool,
    is_unavailable_result,
    result_error,
    tool_result_message,
)
from api.app.agent.tool_rag import load_full_tool_schema
from api.app.db.models import AgentPlan, AgentPlanStep, AgentRun
from api.app.db.plan_store import (
    get_agent_plan,
    insert_agent_run,
    list_agent_plan_steps,
)
from api.app.logging_config import get_logger, log_tool_rag_activity

logger = get_logger("api.agent.executor")

_EXECUTOR_SYSTEM = (
    "You are the execution agent. Given the user question and tool results, "
    "write the final user-facing answer. Use only the provided tool results; "
    "do not invent facts. Keep the answer concise and concrete."
)


def _chat_model(extra: dict[str, Any]) -> ChatModel:
    model = extra.get("chat_model")
    if model is not None:
        return model
    force_stub = bool(extra.get("force_stub"))
    return get_chat_model(force_stub=force_stub)


def _compose_final_answer(
    *,
    context: AgentContext,
    extra: dict[str, Any],
    evidence_lines: list[str],
    fallback: str,
) -> str:
    """LLM final answer from tool results; falls back to joined tool text."""
    evidence = "\n\n".join(line for line in evidence_lines if line).strip()
    if not evidence and not (context.question or "").strip():
        return fallback
    user = (
        f"Question: {context.question or ''}\n\n"
        f"Tool results:\n{evidence or '(none)'}"
    )
    try:
        result = _chat_model(extra).complete(
            system=_EXECUTOR_SYSTEM,
            messages=[{"role": "user", "content": user}],
            model_tier="fast",
        )
    except Exception:
        logger.exception(
            "executor_compose_failed client_id=%s", context.client_id
        )
        return fallback
    text = (result.text or "").strip()
    return text or fallback


def _session(extra: dict[str, Any]) -> tuple[Session, bool]:
    db = extra.get("db")
    if db is not None:
        return db, False
    factory = extra.get("db_factory")
    if callable(factory):
        return factory(), True
    from api.app.db.session import SessionLocal

    return SessionLocal(), True


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _finish_run(
    plan: AgentPlan,
    run: AgentRun,
    *,
    status: str,
    error: str | None,
) -> None:
    plan.status = status
    run.status = status
    run.error = error
    run.finished_at = _now()


def _halt_step(
    step: AgentPlanStep,
    *,
    result_key: str,
    message: str,
) -> None:
    step.status = "succeeded"
    step.result = {result_key: message}
    step.error = None


def _skip_remaining(steps: list[AgentPlanStep], start_index: int) -> None:
    for pending in steps[start_index + 1 :]:
        if pending.status == "pending":
            pending.status = "skipped"


class ExecutorAgent(Agent):
    """Sequential executor. Runs plan steps in order with precondition gates."""

    @property
    def role(self) -> str:
        return "executor"

    def _run_impl(self, context: AgentContext) -> AgentResult:
        extra = dict(context.extra or {})
        plan_id = extra.get("plan_id")
        if not plan_id:
            return AgentResult(
                role=self.role,
                client_id=context.client_id,
                status="failed",
                message="plan_id is required",
            )
        db, own_session = _session(extra)
        try:
            return self._execute(context, db, extra, plan_id)
        finally:
            if own_session:
                db.close()

    def _execute(
        self,
        context: AgentContext,
        db: Session,
        extra: dict[str, Any],
        plan_id: Any,
    ) -> AgentResult:
        plan = get_agent_plan(
            db, tenant_id=context.client_id, plan_id=plan_id
        )
        if plan is None:
            return AgentResult(
                role=self.role,
                client_id=context.client_id,
                status="failed",
                message="plan not found for this tenant",
                extra={"plan_id": str(plan_id)},
            )

        run = insert_agent_run(
            db,
            tenant_id=context.client_id,
            plan_id=plan.id,
            status="running",
        )
        run.started_at = _now()
        plan.status = "running"
        db.flush()

        steps = list_agent_plan_steps(
            db, tenant_id=context.client_id, plan_id=plan.id
        )
        exec_ctx = ExecutionContext.from_agent_context(
            client_id=context.client_id,
            attachments=context.attachments,
            plan_source=plan.source if isinstance(plan.source, dict) else None,
        )
        discovery = DbToolDiscovery(db, extra)

        output_lines: list[str] = []
        step_results: dict[str, Any] = {}
        for index, step in enumerate(steps):
            meta = step_meta(step.arguments)
            step_type = infer_step_type(step.tool_name or "", meta)
            tool_name = (step.tool_name or "").strip()

            ok, reason = check_preconditions(
                meta.get("preconditions") or {}, exec_ctx
            )
            if not ok:
                message = precondition_fail_message(meta, reason)
                step.status = "skipped"
                step.error = reason
                step.result = {"precondition_failed": message}
                _skip_remaining(steps, index)
                _finish_run(plan, run, status="succeeded", error=None)
                db.commit()
                return AgentResult(
                    role=self.role,
                    client_id=context.client_id,
                    status="succeeded",
                    message=message,
                    extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                )

            if step_type == STEP_TYPE_HALT:
                message = step_message(step.arguments) or "execution halted"
                _halt_step(step, result_key="halt", message=message)
                output_lines.append(message)
                _skip_remaining(steps, index)
                _finish_run(plan, run, status="succeeded", error=None)
                db.commit()
                return AgentResult(
                    role=self.role,
                    client_id=context.client_id,
                    status="succeeded",
                    message=message,
                    extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                )

            if step_type == STEP_TYPE_ADVICE:
                message = step_message(step.arguments)
                _halt_step(step, result_key="advice", message=message)
                if message:
                    output_lines.append(message)
                if meta.get("stop_after"):
                    _skip_remaining(steps, index)
                    final = "\n\n".join(output_lines).strip() or "plan executed"
                    _finish_run(plan, run, status="succeeded", error=None)
                    db.commit()
                    return AgentResult(
                        role=self.role,
                        client_id=context.client_id,
                        status="succeeded",
                        message=final,
                        extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                    )
                db.flush()
                continue

            if step_type != STEP_TYPE_TOOL:
                step.status = "failed"
                step.error = f"unknown step type: {step_type}"
                _skip_remaining(steps, index)
                _finish_run(plan, run, status="failed", error=step.error)
                db.commit()
                return AgentResult(
                    role=self.role,
                    client_id=context.client_id,
                    status="failed",
                    message=step.error,
                    extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                )

            if not tool_name:
                step.status = "failed"
                step.error = "empty tool_name"
                _skip_remaining(steps, index)
                _finish_run(plan, run, status="failed", error=step.error)
                db.commit()
                return AgentResult(
                    role=self.role,
                    client_id=context.client_id,
                    status="failed",
                    message=step.error,
                    extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                )

            ref = discovery.find(tool_name, client_id=context.client_id)
            if ref is None:
                error_msg = f"tool not found: {tool_name}"
                step.status = "failed"
                step.error = error_msg
                _skip_remaining(steps, index)
                _finish_run(plan, run, status="failed", error=error_msg)
                db.commit()
                return AgentResult(
                    role=self.role,
                    client_id=context.client_id,
                    status="failed",
                    message=error_msg,
                    extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                )

            # Lazy-load full schema/config only after the tool is chosen.
            full_schema = load_full_tool_schema(ref)
            log_tool_rag_activity(
                phase="executor_resolve",
                client_id=context.client_id,
                plan_id=str(plan.id),
                step_index=index,
                tool_name=ref.name,
                kind=ref.kind,
                source=ref.source,
                has_subcommands=bool(full_schema.get("subcommands")),
            )

            step.status = "running"
            db.flush()
            invoke_args = tool_arguments(step.arguments)
            if step_results:
                invoke_args = {
                    **invoke_args,
                    "prior_step_results": dict(step_results),
                }

            try:
                result = invoke_tool(
                    ref,
                    invoke_args,
                    client_id=context.client_id,
                    db=db,
                    extra=extra,
                )
            except ToolExecutionError as exc:
                error_msg = str(exc)
                step.status = "failed"
                step.error = error_msg
                _skip_remaining(steps, index)
                _finish_run(plan, run, status="failed", error=error_msg)
                db.commit()
                return AgentResult(
                    role=self.role,
                    client_id=context.client_id,
                    status="failed",
                    message=error_msg,
                    extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                )

            if is_unavailable_result(result):
                note = tool_result_message(tool_name, result)
                step.status = "skipped"
                step.error = note
                step.result = result
                output_lines.append(note)
                db.flush()
                continue

            failed = result_error(result)
            if failed:
                step.status = "failed"
                step.error = failed
                step.result = result
                _skip_remaining(steps, index)
                _finish_run(plan, run, status="failed", error=failed)
                db.commit()
                return AgentResult(
                    role=self.role,
                    client_id=context.client_id,
                    status="failed",
                    message=failed,
                    extra={"plan_id": str(plan.id), "run_id": str(run.id)},
                )

            step.status = "succeeded"
            step.result = result
            step.error = None
            step_results[tool_name] = result
            step_results[f"step_{index}"] = result
            text = tool_result_message(tool_name, result)
            if text:
                output_lines.append(text)
            db.flush()

        final_message = "\n\n".join(output_lines).strip() or "plan executed"
        if output_lines:
            final_message = _compose_final_answer(
                context=context,
                extra=extra,
                evidence_lines=output_lines,
                fallback=final_message,
            )
        _finish_run(plan, run, status="succeeded", error=None)
        db.commit()
        return AgentResult(
            role=self.role,
            client_id=context.client_id,
            status="succeeded",
            message=final_message,
            extra={"plan_id": str(plan.id), "run_id": str(run.id)},
        )

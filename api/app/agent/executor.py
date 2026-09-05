"""Executor Agent (Sprint 48). Sequential plan execution with tool calling.

Loads a persisted plan and runs steps one at a time in order. Before each
step, preconditions are checked against runtime context (attachments, etc.).
Advice and halt steps produce user-facing output; halt and failed
preconditions stop the run without executing later steps.

Plain-English goal steps delegate to the ReAct engine, which acts inside a
single isolated workspace shared by the run: inputs are staged copies, so each
step's produced artifacts are attributable and the user's originals cannot be
mutated in place. Produced files are promoted to durable storage at the end.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from api.app.agent.base import Agent, AgentContext, AgentResult
from api.app.agent.llm import (
    ChatModel,
    get_chat_model,
)
from api.app.agent.plan_steps import (
    RUN_UVX_TOOL_NAME,
    STEP_TYPE_ADVICE,
    STEP_TYPE_HALT,
    STEP_TYPE_TOOL,
    ExecutionContext,
    check_preconditions,
    english_instruction,
    infer_step_type,
    is_english_goal_step,
    precondition_fail_message,
    step_message,
    step_meta,
    tool_arguments,
)
from api.app.agent.tools import (
    DbToolDiscovery,
    ToolExecutionError,
    invoke_tool,
    is_unavailable_result,
    lookup_tool,
    result_error,
    tool_result_message,
)
from api.app.agent.tool_rag import load_full_tool_schema
from api.app.agent.react import StepBudget, StepRequest, run_goal_step
from api.app.agent.uvx_runner import run_uvx_from_arguments
from api.app.agent.workspace import (
    RunWorkspace,
    create_run_workspace,
    promote_outputs,
)
from api.app.db.models import AgentPlan, AgentPlanStep, AgentRun
from api.app.db.plan_store import (
    get_agent_plan,
    insert_agent_run,
    list_agent_plan_steps,
)
from api.app.agent.outcome_verifier import (
    capture_working_scope,
    combine_results_for_plan_check,
    criteria_text,
    existing_files_in_scope,
    has_contract,
    verify_step_outcome,
)
from api.app.logging_config import get_logger, log_tool_rag_activity

logger = get_logger("api.agent.executor")

_EXECUTOR_SYSTEM = (
    "You are the execution agent composing the final user-facing answer. "
    "Given the user's question and evidence from completed steps, write a clear, "
    "accurate reply. Use only the provided evidence; do not invent facts. "
    "When steps created or referenced files, mention their paths. "
    "Keep the answer concise and actionable."
)

def _executor_settings(extra: dict[str, Any]) -> Any:
    settings = extra.get("settings")
    if settings is None:
        from api.app.settings import get_settings

        settings = get_settings()
    return settings


def _resolve_working_dir(context: AgentContext, arguments: dict[str, Any]) -> str | None:
    def _as_dir(raw: object) -> str | None:
        text = str(raw or "").strip()
        if not text:
            return None
        path = Path(text)
        if path.is_dir():
            return str(path.resolve())
        if path.is_file():
            return str(path.parent.resolve())
        # Not on disk yet — if it looks like a file, use parent
        if path.suffix:
            return str(path.parent.resolve()) if str(path.parent) not in {"", "."} else None
        return str(path.resolve())

    for key in ("cwd", "working_dir"):
        resolved = _as_dir(arguments.get(key))
        if resolved:
            return resolved
    # local_path on args/attachments is often a file; use its parent directory
    resolved = _as_dir(arguments.get("local_path"))
    if resolved:
        return resolved
    for att in context.attachments or []:
        if not isinstance(att, dict):
            continue
        for key in ("working_dir", "local_path", "path"):
            resolved = _as_dir(att.get(key))
            if resolved:
                return resolved
    return None


def _execute_run_uvx_call(
    arguments: dict[str, Any],
    *,
    context: AgentContext,
    extra: dict[str, Any],
    db: Session,
    prior_attempts: list[dict[str, Any]] | None = None,
    instruction: str = "",
    success_criteria: str = "",
) -> dict[str, Any]:
    """Prefer injected test tool; otherwise call real uvx_runner with recovery."""
    args = dict(arguments or {})
    cwd = _resolve_working_dir(context, args)
    if cwd and "cwd" not in args:
        args["cwd"] = cwd
    injected = lookup_tool(
        RUN_UVX_TOOL_NAME, client_id=context.client_id, db=db, extra=extra
    )
    if injected is not None and injected.source == "injected" and injected.invoke:
        return invoke_tool(
            injected, args, client_id=context.client_id, db=db, extra=extra
        )
    return run_uvx_from_arguments(
        args,
        prior_attempts=prior_attempts,
        attachments=list(context.attachments or []),
        instruction=instruction,
        success_criteria=success_criteria,
    )


def _summarize_step_result(val: dict[str, Any]) -> str:
    """Compact, tool-agnostic summary of one prior step result."""
    parts: list[str] = []
    if val.get("ok") is True:
        parts.append("status: succeeded")
    elif val.get("ok") is False:
        err = str(val.get("error") or "failed").strip()
        parts.append(f"status: failed ({err})")

    for key in ("output_file", "path", "done_text"):
        text = str(val.get(key) or "").strip()
        if text:
            parts.append(f"{key}: {text}")

    attempts = val.get("attempts")
    if isinstance(attempts, list) and not any(
        p.startswith(("output_file:", "path:")) for p in parts
    ):
        for attempt in reversed(attempts):
            if not isinstance(attempt, dict) or not attempt.get("ok"):
                continue
            artifact = str(
                attempt.get("output_file") or attempt.get("path") or ""
            ).strip()
            if artifact:
                parts.append(f"output_file: {artifact}")
                break

    stdout = str(val.get("stdout") or "").strip()
    if stdout:
        parts.append(f"stdout:\n{stdout[:2000]}")

    return "\n".join(parts)


def _format_prior_step_results(prior: dict[str, Any] | None) -> str:
    if not isinstance(prior, dict) or not prior:
        return "(none)"
    chunks: list[str] = []
    for key, val in list(prior.items())[:8]:
        if isinstance(val, dict):
            snippet = _summarize_step_result(val)
        else:
            snippet = str(val)[:1000]
        if snippet.strip():
            chunks.append(f"[{key}]\n{snippet}")
    return "\n\n".join(chunks) if chunks else "(none)"


def _workspace_run_key(extra: dict[str, Any]) -> str:
    plan_id = str(extra.get("plan_id") or "").strip()
    return plan_id or f"run-{_now().strftime('%Y%m%d%H%M%S%f')}"


def _step_workspace(
    context: AgentContext,
    extra: dict[str, Any],
    step_arguments: dict[str, Any],
) -> RunWorkspace:
    """The one workspace shared by every step of this run."""
    existing = extra.get("workspace")
    if isinstance(existing, RunWorkspace):
        return existing

    # An explicitly supplied directory is adopted as-is so callers can pin
    # execution to a prepared location.
    pinned = None
    for key in ("workspace_dir", "cwd", "working_dir"):
        raw = str(step_arguments.get(key) or "").strip()
        if raw and Path(raw).is_dir():
            pinned = Path(raw).resolve()
            break
    if pinned is not None:
        workspace = RunWorkspace(root=pinned, inputs=())
        workspace.scripts_dir.mkdir(parents=True, exist_ok=True)
        extra["workspace"] = workspace
        return workspace

    workspace = create_run_workspace(
        client_id=context.client_id,
        run_key=_workspace_run_key(extra),
        attachments=list(context.attachments or []),
        settings=_executor_settings(extra),
    )
    extra["workspace"] = workspace
    return workspace


def _action_overrides(extra: dict[str, Any]) -> dict[str, Any]:
    """Injected action implementations (tests and registry-backed hosts)."""
    tools = extra.get("tools")
    if not isinstance(tools, dict):
        return {}
    overrides: dict[str, Any] = {}
    for name in (RUN_UVX_TOOL_NAME, "run_python", "inspect_workspace"):
        candidate = tools.get(name)
        if callable(candidate):
            overrides[name] = candidate
    return overrides


def _run_english_goal_react(
    *,
    context: AgentContext,
    extra: dict[str, Any],
    db: Session,
    instruction: str,
    success_criteria: Any,
    step_arguments: dict[str, Any],
) -> dict[str, Any]:
    """Run one plain-English goal through the ReAct engine."""
    _ = db
    settings = _executor_settings(extra)
    workspace = _step_workspace(context, extra, step_arguments)
    request = StepRequest(
        instruction=instruction,
        success_criteria=success_criteria,
        question=context.question or "",
        workspace=workspace,
        model=_chat_model(extra),
        settings=settings,
        prior_results=_format_prior_step_results(
            step_arguments.get("prior_step_results")
        ),
        attachments=list(context.attachments or []),
        budget=StepBudget.from_settings(settings),
        action_overrides=_action_overrides(extra),
    )
    return run_goal_step(request)


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
    if not text or text in {
        "All steps completed.",
        "All done.",
        "done",
        "Done.",
    }:
        return fallback
    return text


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


def _attachment_input_paths(context: AgentContext) -> list[Path]:
    paths: list[Path] = []
    for att in context.attachments or []:
        if not isinstance(att, dict):
            continue
        for key in ("local_path", "path"):
            raw = str(att.get(key) or "").strip()
            if not raw:
                continue
            path = Path(raw)
            if path.is_file():
                paths.append(path.resolve())
                break
    return paths


def _log_step_boundary(
    *,
    phase: str,
    context: AgentContext,
    plan_id: str,
    step_index: int,
    tool_name: str,
    scope_dir: str | None,
) -> None:
    snapshot = capture_working_scope(scope_dir)
    log_tool_rag_activity(
        phase="executor_step_boundary",
        client_id=context.client_id,
        boundary_phase=phase,
        plan_id=plan_id,
        step_index=step_index,
        tool_name=tool_name,
        working_scope=snapshot,
    )


_DELIVERED_FILES_KEY = "delivered_files"
_STEP_DIAGNOSTICS_KEY = "step_diagnostics"


def _record_step_diagnostic(
    extra: dict[str, Any],
    *,
    step_index: int,
    tool_name: str,
    status: str,
    result: Any,
) -> None:
    """Keep why a step ended retrievable from the run outcome.

    Loop-level facts such as how many attempts ran and what stopped the loop
    are otherwise only in the database, which puts diagnosis out of reach of
    whoever called the API.
    """
    entry: dict[str, Any] = {
        "step_index": step_index,
        "tool_name": tool_name,
        "status": status,
    }
    if isinstance(result, dict):
        for key in (
            "attempt_count",
            "stop_reason",
            "verification_method",
            "verification_reason",
            "outcome",
        ):
            if result.get(key) is not None:
                entry[key] = result[key]
    extra.setdefault(_STEP_DIAGNOSTICS_KEY, []).append(entry)


def _delivery_destination(context: AgentContext) -> Path | None:
    """Durable location for produced artifacts, derived from the inputs."""
    for att in context.attachments or []:
        if not isinstance(att, dict):
            continue
        for key in ("local_path", "path"):
            raw = str(att.get(key) or "").strip()
            if not raw:
                continue
            parent = Path(raw).parent
            if parent.is_dir():
                return parent.resolve()
    return None


def _promote_run_outputs(
    context: AgentContext,
    extra: dict[str, Any],
) -> list[str]:
    """Copy workspace artifacts out so the user can retrieve them.

    Runs at most once per run, so any number of terminal paths may ask for
    delivery without duplicating or skipping it.
    """
    cached = extra.get(_DELIVERED_FILES_KEY)
    if isinstance(cached, list):
        return list(cached)
    workspace = extra.get("workspace")
    if not isinstance(workspace, RunWorkspace):
        return []
    destination = _delivery_destination(context)
    if destination is None:
        return []
    try:
        promoted = promote_outputs(workspace, destination=destination)
    except OSError:
        logger.exception(
            "executor_promote_failed client_id=%s", context.client_id
        )
        return []
    extra[_DELIVERED_FILES_KEY] = list(promoted)
    return promoted


def _final_goal_step(steps: list[AgentPlanStep]) -> AgentPlanStep | None:
    for step in reversed(steps):
        meta = step_meta(step.arguments)
        step_type = infer_step_type(step.tool_name or "", meta)
        if step_type in (STEP_TYPE_ADVICE, STEP_TYPE_HALT):
            continue
        if (step.tool_name or "").strip():
            return step
    return None


def _plan_goal_verification(
    *,
    steps: list[AgentPlanStep],
    step_results: dict[str, Any],
    current_result: dict[str, Any],
    context: AgentContext,
    invoke_args: dict[str, Any],
    known_inputs: list | None = None,
    baseline_files: set | None = None,
    scope_dir: str | None = None,
):
    final = _final_goal_step(steps)
    if final is None:
        return None
    if not has_contract(final.success_criteria):
        return None
    merged = combine_results_for_plan_check(step_results)
    for key in ("output_file", "path", "stdout", "done_text", "attempts"):
        if current_result.get(key) and not merged.get(key):
            merged[key] = current_result.get(key)
    if current_result.get("ok"):
        merged["ok"] = True
    instruction = english_instruction(tool_arguments(final.arguments)) or criteria_text(
        final.success_criteria
    )
    cwd = scope_dir or _resolve_working_dir(context, invoke_args)
    return verify_step_outcome(
        success_criteria=final.success_criteria,
        instruction=instruction,
        result=merged,
        scope_dir=cwd,
        known_inputs=known_inputs,
        baseline_files=baseline_files,
    )


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
            return self._deliver(
                context, extra, self._execute(context, db, extra, plan_id)
            )
        finally:
            if own_session:
                db.close()

    def _deliver(
        self,
        context: AgentContext,
        extra: dict[str, Any],
        result: AgentResult,
    ) -> AgentResult:
        """Report produced artifacts on every terminal path.

        What a run produced is observable independently of whether the outcome
        check passed, so routing all outcomes through here keeps a negative
        verdict from hiding finished work.
        """
        diagnostics = extra.get(_STEP_DIAGNOSTICS_KEY)
        if diagnostics:
            result.extra = {
                **(result.extra or {}),
                _STEP_DIAGNOSTICS_KEY: list(diagnostics),
            }
        promoted = _promote_run_outputs(context, extra)
        if not promoted:
            return result
        result.extra = {**(result.extra or {}), _DELIVERED_FILES_KEY: promoted}
        if result.status != "succeeded":
            note = "Files produced before the run stopped:\n" + "\n".join(promoted)
            result.message = (
                f"{result.message}\n\n{note}".strip() if result.message else note
            )
        return result

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

            step.status = "running"
            db.flush()
            invoke_args = tool_arguments(step.arguments)
            if step_results:
                invoke_args = {
                    **invoke_args,
                    "prior_step_results": dict(step_results),
                }
            english_goal = is_english_goal_step(tool_name, invoke_args)
            if english_goal:
                # Goal steps are verified against the isolated workspace, so a
                # produced artifact is provably this step's work.
                workspace = _step_workspace(context, extra, invoke_args)
                step_cwd = str(workspace.root)
                known_inputs = [p for p in workspace.input_paths if p.is_file()]
            else:
                step_cwd = _resolve_working_dir(context, invoke_args)
                known_inputs = _attachment_input_paths(context)
            baseline_files = existing_files_in_scope(step_cwd)
            _log_step_boundary(
                phase="start",
                context=context,
                plan_id=str(plan.id),
                step_index=index,
                tool_name=tool_name,
                scope_dir=step_cwd,
            )
            step_criteria = criteria_text(step.success_criteria)

            try:
                if english_goal:
                    instruction = english_instruction(invoke_args) or (
                        step_criteria or tool_name
                    )
                    log_tool_rag_activity(
                        phase="executor_english_goal",
                        client_id=context.client_id,
                        plan_id=str(plan.id),
                        step_index=index,
                        tool_name=tool_name,
                        instruction=instruction[:200],
                    )
                    result = _run_english_goal_react(
                        context=context,
                        extra=extra,
                        db=db,
                        instruction=instruction,
                        success_criteria=step.success_criteria,
                        step_arguments=invoke_args,
                    )
                elif tool_name == RUN_UVX_TOOL_NAME:
                    log_tool_rag_activity(
                        phase="executor_run_uvx",
                        client_id=context.client_id,
                        plan_id=str(plan.id),
                        step_index=index,
                        tool_name=tool_name,
                    )
                    result = _execute_run_uvx_call(
                        invoke_args, context=context, extra=extra, db=db
                    )
                    if isinstance(result, dict):
                        result.setdefault("attempt_count", 1)
                else:
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

            instruction_for_verify = None
            if english_goal:
                instruction_for_verify = (
                    english_instruction(invoke_args) or step_criteria or tool_name
                )

            _log_step_boundary(
                phase="end",
                context=context,
                plan_id=str(plan.id),
                step_index=index,
                tool_name=tool_name,
                scope_dir=step_cwd,
            )

            if isinstance(result, dict) and (english_goal or step_criteria):
                verification = verify_step_outcome(
                    success_criteria=step.success_criteria,
                    instruction=instruction_for_verify,
                    result=result,
                    scope_dir=step_cwd,
                    known_inputs=known_inputs,
                    baseline_files=baseline_files,
                )
                result = {
                    **result,
                    "verification_method": verification.method,
                    "verification_reason": verification.reason,
                }
                if verification.verified and not result.get("ok"):
                    result["ok"] = True
                    result["verified"] = True
                    result["outcome"] = "succeeded"
                elif not verification.verified:
                    result["ok"] = False
                    result["error"] = verification.reason
                    result["outcome"] = (
                        "partial" if verification.partial else "failed"
                    )

            failed = result_error(result)
            if failed:
                plan_check = _plan_goal_verification(
                    steps=steps,
                    step_results=step_results,
                    current_result=result if isinstance(result, dict) else {},
                    context=context,
                    invoke_args=invoke_args,
                    known_inputs=known_inputs,
                    baseline_files=baseline_files,
                    scope_dir=step_cwd,
                )
                if plan_check is not None and plan_check.verified:
                    step.status = "skipped"
                    step.error = failed
                    step.result = {
                        **(result if isinstance(result, dict) else {"error": failed}),
                        "plan_level_success": True,
                        "verification_method": plan_check.method,
                        "verification_reason": plan_check.reason,
                    }
                    _skip_remaining(steps, index)
                    final_message = "\n\n".join(output_lines).strip() or plan_check.reason
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
                step.status = "failed"
                step.error = failed
                step.result = result
                _record_step_diagnostic(
                    extra,
                    step_index=index,
                    tool_name=tool_name,
                    status="failed",
                    result=result,
                )
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
            _record_step_diagnostic(
                extra,
                step_index=index,
                tool_name=tool_name,
                status="succeeded",
                result=result,
            )
            step_results[tool_name] = result
            step_results[f"step_{index}"] = result
            text = tool_result_message(tool_name, result)
            if text:
                output_lines.append(text)
            db.flush()

        promoted = _promote_run_outputs(context, extra)
        if promoted:
            output_lines.append(
                "Files delivered:\n" + "\n".join(promoted)
            )
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

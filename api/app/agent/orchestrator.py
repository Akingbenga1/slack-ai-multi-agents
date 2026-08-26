"""Orchestrator Agent (Sprint 44). Plans only — never runs work tools.

Gather is read-only (attachments metadata, tenant-scoped library documents).
After gather, one ``agent_plans`` row and N ``agent_plan_steps`` are written.
The executor is not invoked here.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.agent.base import Agent, AgentContext, AgentResult
from api.app.agent.gather import GatheredContext, gather
from api.app.agent.guardrails import (
    PLAN_SAFETY_REFUSAL,
    find_destructive_plan_violations,
)
from api.app.agent.llm import ChatModel, get_chat_model
from api.app.agent.plan_steps import (
    ADVICE_STEP_TOOL_NAME,
    HALT_STEP_TOOL_NAME,
    STEP_TYPE_ADVICE,
    STEP_TYPE_HALT,
    STEP_TYPE_TOOL,
    arguments_with_meta,
    extract_on_precondition_fail,
    extract_preconditions,
)
from api.app.agent.tool_rag import (
    build_retrieval_query,
    get_tool_rag,
    skinny_catalog,
    summarize_workflow_body,
)
from api.app.agent.tools import DbToolDiscovery, ToolDiscovery, ToolRef
from api.app.db.plan_store import insert_agent_plan, insert_agent_plan_step
from api.app.logging_config import get_logger, log_tool_rag_activity

logger = get_logger("api.agent.orchestrator")

_PLAN_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.S)

_PLAN_SYSTEM = (
    "You are a planning agent. Produce a JSON execution plan only. "
    "Do not execute tools, post to Slack, send email, generate PDF or PPTX, "
    "or mutate a workflow library. "
    "The user message includes a shortlisted tool catalog retrieved for this request "
    "(skinny rows: name, kind, and one short description only — not the full tenant "
    "registry, and not full CLI/MCP schemas). "
    "Read each tool's name, kind, and description and choose only the tools needed "
    "for the request. "
    "Every step tool_name MUST exactly match a catalog name — never invent, rename, "
    "or hallucinate tools that are not in the shortlist. "
    "Full CLI subcommands and large schemas are loaded later at execution time. "
    "When a step needs a CLI tool, set arguments with a best-effort "
    "\"subcommand\" and \"args_list\" (array of CLI arguments after the subcommand, "
    "e.g. input/output paths) derived from the user request. "
    "For file-producing CLI steps you may also set \"output_file\" or "
    "\"expected_output_path\". "
    "Do not invent registry default args — derive args_list from the user request. "
    "Assign a catalog tool to a step only when you judge that tool can genuinely "
    "implement that step — never invent tool names, and never assign a tool merely "
    "because it is the only one listed (for example, do not use csvkit for work it "
    "cannot perform, such as document summarization or Slack posting). "
    "When a stored workflow body is provided, treat it as the primary guide: read "
    "its steps and rules, decide which document steps any catalog tool can implement, "
    "derive success criteria from the document, and apply user overrides (skip listed "
    "steps; change channels; fill run-specific args). "
    "Include only steps where a catalog tool is a reasonable fit. "
    "When a workflow document step has no suitable catalog tool, do not force a "
    "mismatched tool (for example csvkit for document summarization). Instead "
    "include an advice step: "
    "{\"step_type\": \"advice\", \"advice\": \"<guidance or alternative>\", "
    "\"success_criteria\": \"...\"}. "
    "Advice steps need no catalog tool — use them for gaps, alternatives, or "
    "guidance when a document step cannot be automated yet. "
    "Prefer a mix of tool steps and advice steps when the workflow body spans both "
    "automatable and non-automatable work. "
    "CONTROL FLOW (mandatory for runtime checks): "
    "Any step may declare preconditions, e.g. "
    "\"requires_attachment\": true or \"requires\": [\"attachment\"]. "
    "When a step needs runtime context the user may lack (no attachment, no file), "
    "either add preconditions plus \"on_precondition_fail\": \"<user message>\", "
    "or emit a dedicated halt step and omit all later steps. "
    "Halt steps use step_type \"halt\" with \"message\" (or \"advice\") — they stop "
    "execution with that user-facing text. "
    "Do not plan tool steps that would run after a precondition you know will fail "
    "given the attachment metadata in the user message. "
    "Advice steps may set \"stop_after\": true when they block further work; "
    "otherwise later tool steps may still run. "
    "Reply with JSON: {\"workflow\": \"<type>\", \"steps\": [{\"tool_name\": \"...\", "
    "\"arguments\": {}, \"success_criteria\": \"...\", "
    "\"requires_attachment\": false}, "
    "{\"step_type\": \"advice\", \"advice\": \"...\", \"success_criteria\": \"...\"}, "
    "{\"step_type\": \"halt\", \"message\": \"...\"}]}. "
    "SAFETY GUARDRAILS (mandatory — never violate): "
    "NEVER plan steps that delete, remove, truncate, drop, purge, wipe, erase, "
    "destroy, unlink, or overwrite existing files, directories, blobs, uploads, "
    "attachments, or workflow-library originals. "
    "Creating or uploading new output files is allowed; deleting or replacing "
    "existing stored data is forbidden. "
    "NEVER plan database mutations that DELETE rows, DROP or TRUNCATE tables or "
    "schemas, or run destructive SQL (DELETE, DROP, TRUNCATE, ALTER ... DROP). "
    "Read-only DB access (SELECT, list, get, search) is allowed. "
    "NEVER plan shell or CLI steps whose purpose is deletion (rm, del, rmdir, "
    "unlink, shred, or equivalent). "
    "If the user asks to delete files, rows, tables, or other stored data — even "
    "when a matching tool exists — refuse: return "
    "{\"workflow\": \"qa\", \"steps\": []}. "
    "Prefer read-only, additive, or compose-only steps: fetch, search, list, get, "
    "download, parse, summarize, compose, create (new artifacts), upload (new files)."
)


def _session(extra: dict[str, Any]) -> tuple[Session, bool]:
    db = extra.get("db")
    if db is not None:
        return db, False
    factory = extra.get("db_factory")
    if callable(factory):
        return factory(), True
    from api.app.db.session import SessionLocal

    return SessionLocal(), True


def _chat_model(extra: dict[str, Any]) -> ChatModel:
    injected = extra.get("chat_model")
    if injected is not None:
        return injected
    return get_chat_model()


def parse_plan(raw: str) -> tuple[str, list[dict[str, Any]]]:
    """Parse workflow and steps from model JSON. Returns (workflow, steps)."""
    text = (raw or "").strip()
    if not text:
        return "qa", []
    candidates = [text]
    fenced = _PLAN_JSON_RE.search(text)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    parsed: Any = None
    for blob in candidates:
        try:
            parsed = json.loads(blob)
            break
        except json.JSONDecodeError:
            continue
    if parsed is None:
        return "qa", []
    workflow = "qa"
    if isinstance(parsed, dict):
        workflow = str(parsed.get("workflow") or "qa").strip() or "qa"
        items = parsed.get("steps", [])
        if not isinstance(items, list):
            return workflow, []
    elif isinstance(parsed, list):
        items = parsed
    else:
        return "qa", []
    steps: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        step_type = str(item.get("step_type") or STEP_TYPE_TOOL).strip().lower()
        criteria = item.get("success_criteria")
        if criteria is None:
            criteria = item.get("success")
        preconditions = extract_preconditions(item)
        on_precondition_fail = extract_on_precondition_fail(item)
        stop_after = item.get("stop_after")
        message_text = str(
            item.get("advice") or item.get("message") or item.get("text") or ""
        ).strip()
        if step_type == STEP_TYPE_HALT:
            if message_text:
                steps.append(
                    {
                        "tool_name": HALT_STEP_TOOL_NAME,
                        "arguments": {"text": message_text},
                        "success_criteria": criteria,
                        "step_type": STEP_TYPE_HALT,
                        "preconditions": preconditions,
                        "on_precondition_fail": on_precondition_fail,
                        "stop_after": True,
                    }
                )
            continue
        if step_type == STEP_TYPE_ADVICE or (
            not str(item.get("tool_name") or item.get("name") or "").strip()
            and message_text
        ):
            if message_text:
                step_payload: dict[str, Any] = {
                    "tool_name": ADVICE_STEP_TOOL_NAME,
                    "arguments": {"text": message_text},
                    "success_criteria": criteria,
                    "step_type": STEP_TYPE_ADVICE,
                    "preconditions": preconditions,
                }
                if on_precondition_fail:
                    step_payload["on_precondition_fail"] = on_precondition_fail
                if stop_after is not None:
                    step_payload["stop_after"] = bool(stop_after)
                steps.append(step_payload)
            continue
        name = str(item.get("tool_name") or item.get("name") or "").strip()
        if not name:
            continue
        raw_args = item.get("arguments")
        args = raw_args if isinstance(raw_args, dict) else {}
        tool_step: dict[str, Any] = {
            "tool_name": name,
            "arguments": args or {},
            "success_criteria": criteria,
            "step_type": STEP_TYPE_TOOL,
            "preconditions": preconditions,
        }
        if on_precondition_fail:
            tool_step["on_precondition_fail"] = on_precondition_fail
        if stop_after is not None:
            tool_step["stop_after"] = bool(stop_after)
        steps.append(tool_step)
    return workflow, steps


def parse_plan_steps(raw: str) -> list[dict[str, Any]]:
    """Parse JSON steps from model text. Empty list if none are usable."""
    _, steps = parse_plan(raw)
    return steps


def _tool_discovery(db: Session, extra: dict[str, Any]) -> ToolDiscovery:
    injected = extra.get("tool_discovery")
    if injected is not None:
        return injected
    return DbToolDiscovery(db, extra)


def _tool_catalog(refs: list[ToolRef]) -> list[dict[str, Any]]:
    """Skinny planner rows only — never paste full CLI/MCP schemas here."""
    catalog: list[dict[str, Any]] = []
    for ref in sorted(refs, key=lambda item: item.name):
        entry: dict[str, Any] = {"name": ref.name}
        if ref.kind:
            entry["kind"] = ref.kind
        description = (ref.description or "").strip()
        if description:
            entry["description"] = description
        catalog.append(entry)
    return catalog


def _workflow_body_for_prompt(
    gathered: GatheredContext,
    *,
    max_chars: int,
    client_id: str | None = None,
) -> str:
    body = str((gathered.workflow or {}).get("body_text") or "")
    return summarize_workflow_body(
        body,
        query=gathered.question,
        max_chars=max_chars,
        client_id=client_id,
    )


def _planning_user_message(
    gathered: GatheredContext,
    *,
    tool_catalog: list[dict[str, Any]],
    workflow_body_max_chars: int = 1500,
    client_id: str | None = None,
) -> str:
    parts = [f"User request:\n{gathered.question}"]
    if tool_catalog:
        parts.append(
            "Shortlisted tool catalog for this request "
            "(skinny rows only — choose tool_name from this list; full schemas "
            "load at execution):\n"
            + json.dumps(tool_catalog, indent=2)
        )
    else:
        parts.append(
            "Shortlisted tool catalog for this request: none. "
            "You cannot assign tool_name values without shortlisted tools — "
            "do not invent tool names."
        )
    if gathered.attachments:
        parts.append(
            "Attachment metadata (do not assume file contents):\n"
            + json.dumps(gathered.attachments)
        )
    if gathered.workflow:
        parts.append(
            "Stored workflow document (read-only; summarized when long; "
            "do not edit the original):\n"
            + json.dumps(
                {
                    "id": gathered.workflow.get("id"),
                    "title": gathered.workflow.get("title"),
                    "body_text": _workflow_body_for_prompt(
                        gathered,
                        max_chars=workflow_body_max_chars,
                        client_id=client_id,
                    ),
                }
            )
        )
        parts.append(
            "Use the stored workflow document body as the source of truth. Read its "
            "steps and rules, then decide which document steps any catalog tool can "
            "implement. Assign a tool only when it can genuinely help — do not force "
            "a listed tool (e.g. csvkit) onto work it cannot perform. "
            "For document steps no catalog tool can serve, add an advice step "
            "(step_type \"advice\") with guidance or an alternative instead of "
            "omitting the step. Apply user overrides (skip listed steps; change "
            "channels; fill run-specific args)."
        )
    if gathered.channel_names:
        parts.append("Channel names mentioned: " + ", ".join(gathered.channel_names))
    if gathered.channels:
        parts.append("Resolved channel ids: " + json.dumps(gathered.channels))
    parts.append("Return JSON steps only.")
    return "\n\n".join(parts)


def _persist(
    db: Session,
    *,
    tenant_id: str,
    question: str,
    gathered: GatheredContext,
    steps: list[dict[str, Any]],
    status: str,
    error: str | None,
    workflow: str = "qa",
) -> UUID:
    source = gathered.as_source()
    if error:
        source["error"] = error
    plan_json: dict[str, Any] = {"workflow": workflow, "steps": steps}
    if error:
        plan_json["error"] = error
    plan = insert_agent_plan(
        db,
        tenant_id=tenant_id,
        question=question,
        source=source,
        status=status,
        plan_json=plan_json,
    )
    for index, step in enumerate(steps):
        insert_agent_plan_step(
            db,
            tenant_id=tenant_id,
            plan_id=plan.id,
            step_index=index,
            tool_name=step["tool_name"],
            arguments=arguments_with_meta(step),
            success_criteria=step.get("success_criteria"),
            status="pending",
        )
    db.commit()
    return plan.id


class OrchestratorAgent(Agent):
    """Plans only. Gather is read-only; work tools are never executed."""

    @property
    def role(self) -> str:
        return "orchestrator"

    def _run_impl(self, context: AgentContext) -> AgentResult:
        extra = dict(context.extra or {})
        db, own_session = _session(extra)
        try:
            return self._plan(context, db, extra)
        finally:
            if own_session:
                db.close()

    def _plan(
        self,
        context: AgentContext,
        db: Session,
        extra: dict[str, Any],
    ) -> AgentResult:
        lookup: Callable[[str], str | None] | None = extra.get("channel_lookup")
        gathered = gather(
            context.question,
            client_id=context.client_id,
            attachments=list(context.attachments or []),
            extra=extra,
            db=db,
            channel_lookup=lookup,
        )
        if gathered.wants_stored_workflow and gathered.workflow is None:
            error = (
                gathered.workflow_error
                or "No stored workflow matched this request."
            )
            plan_id = _persist(
                db,
                tenant_id=context.client_id,
                question=context.question,
                gathered=gathered,
                steps=[],
                status="failed",
                error=error,
                workflow="qa",
            )
            return AgentResult(
                role=self.role,
                client_id=context.client_id,
                status="failed",
                message=error,
                extra={"plan_id": str(plan_id), "workflow": "qa"},
            )

        discovery = _tool_discovery(db, extra)
        settings = extra.get("settings")
        if settings is None:
            from api.app.settings import get_settings

            settings = get_settings()
            extra = {**extra, "settings": settings}

        retrieval_query = build_retrieval_query(
            gathered.question,
            attachments=gathered.attachments,
            workflow_title=(
                str((gathered.workflow or {}).get("title") or "") or None
            ),
        )
        rag = get_tool_rag(extra)
        shortlisted = rag.shortlist(
            client_id=context.client_id,
            query=retrieval_query,
            discovery=discovery,
            top_k=int(getattr(settings, "tool_rag_top_k", 12) or 12),
        )
        catalog = skinny_catalog(shortlisted)
        workflow_body_max = int(
            getattr(settings, "tool_rag_workflow_body_chars", 1500) or 1500
        )
        user_prompt = _planning_user_message(
            gathered,
            tool_catalog=catalog,
            workflow_body_max_chars=workflow_body_max,
            client_id=context.client_id,
        )
        log_tool_rag_activity(
            phase="plan_context",
            client_id=context.client_id,
            retrieval_query=retrieval_query,
            shortlist_count=len(catalog),
            shortlist_names=[row.get("name") for row in catalog],
            attachment_count=len(gathered.attachments or []),
            has_workflow=gathered.workflow is not None,
            prompt_chars=len(user_prompt),
            includes_subcommands=False,
        )
        include_trace = bool(extra.get("include_trace"))

        model = _chat_model(extra)
        result = model.complete(
            system=_PLAN_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
            model_tier="capable",
            max_tokens=settings.orchestrator_max_tokens,
        )
        workflow, steps = parse_plan(result.text)
        shortlist_names = {str(row.get("name") or "") for row in catalog}
        planned_tools = [
            str(step.get("tool_name") or "")
            for step in steps
            if str(step.get("tool_name") or "").strip()
        ]
        log_tool_rag_activity(
            phase="plan",
            client_id=context.client_id,
            workflow=workflow,
            step_count=len(steps),
            planned_tools=planned_tools,
            tools_from_shortlist=all(
                name in shortlist_names
                or name in {"advice", "halt"}
                for name in planned_tools
            ),
        )

        def _trace_fields(**more: Any) -> dict[str, Any]:
            if not include_trace:
                return more
            return {
                "orchestrator_system_prompt": _PLAN_SYSTEM,
                "orchestrator_user_prompt": user_prompt,
                "plan_steps": steps,
                "planner_raw": result.text,
                "planner_model": result.model,
                "planner_model_tier": "capable",
                **more,
            }

        safety_violations = find_destructive_plan_violations(steps)
        if safety_violations:
            error = PLAN_SAFETY_REFUSAL
            logger.warning(
                "orchestrator_plan_rejected_destructive client_id=%s violations=%s",
                context.client_id,
                safety_violations,
            )
            plan_id = _persist(
                db,
                tenant_id=context.client_id,
                question=context.question,
                gathered=gathered,
                steps=[],
                status="failed",
                error=error,
                workflow=workflow,
            )
            return AgentResult(
                role=self.role,
                client_id=context.client_id,
                status="failed",
                message=error,
                extra=_trace_fields(
                    plan_id=str(plan_id),
                    workflow=workflow,
                    safety_violations=safety_violations,
                ),
            )
        if not steps:
            error = "Planner did not return usable steps."
            plan_id = _persist(
                db,
                tenant_id=context.client_id,
                question=context.question,
                gathered=gathered,
                steps=[],
                status="failed",
                error=error,
                workflow=workflow,
            )
            return AgentResult(
                role=self.role,
                client_id=context.client_id,
                status="failed",
                message=error,
                extra=_trace_fields(plan_id=str(plan_id), workflow=workflow),
            )

        plan_id = _persist(
            db,
            tenant_id=context.client_id,
            question=context.question,
            gathered=gathered,
            steps=steps,
            status="ready",
            error=None,
            workflow=workflow,
        )
        logger.info(
            "orchestrator_plan_ready client_id=%s plan_id=%s workflow=%s steps=%s",
            context.client_id,
            plan_id,
            workflow,
            len(steps),
        )
        return AgentResult(
            role=self.role,
            client_id=context.client_id,
            status="ready",
            message="plan ready",
            extra=_trace_fields(plan_id=str(plan_id), workflow=workflow),
        )

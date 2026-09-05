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
from api.app.agent.llm import EMPTY_COMPLETION_TEXT, ChatModel, get_chat_model
from api.app.agent.plan_steps import (
    ADVICE_STEP_TOOL_NAME,
    EXECUTE_GOAL_TOOL_NAME,
    HALT_STEP_TOOL_NAME,
    STEP_TYPE_ADVICE,
    STEP_TYPE_HALT,
    STEP_TYPE_TOOL,
    arguments_with_meta,
    extract_on_precondition_fail,
    extract_preconditions,
)
from api.app.agent.tool_rag import summarize_workflow_body
from api.app.db.plan_store import insert_agent_plan, insert_agent_plan_step
from api.app.logging_config import get_logger, log_tool_rag_activity

logger = get_logger("api.agent.orchestrator")

_PLAN_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.S)

_PLAN_SYSTEM = (
    "You are a planning agent. Produce a JSON execution plan only. "
    "Plan only — do not yourself execute tools, post to Slack, send email, or "
    "mutate a workflow library. The Executor produces all output artifacts of "
    "any file type (documents, spreadsheets, presentations, images, archives, "
    "data, and text) by running real tools for each execute_goal step, so never "
    "refuse a request merely because it asks for a particular output format. "
    "Do NOT use a tool registry or tool catalog. Plan in plain English only. "
    "Each work step must use tool_name \"execute_goal\" with arguments.instruction "
    "(plain English) and success_criteria. A short English string is valid. "
    "An object {\"text\": \"<note>\", \"relations\": [{\"type\": \"<kind>\"}]} is "
    "also valid. Allowed relation types only: produced, opens_as, novel_vs_inputs, "
    "preserves_originals, count, size, contains_declared. Include only types that "
    "apply. Use novel_vs_inputs when the request transforms existing inputs. "
    "Do not invent CLI package names, uvx commands, or registry tool ids at plan time — "
    "the Executor chooses packages and runs real uvx later. "
    "When a stored workflow body is provided, treat it as the primary guide: read "
    "its steps and rules, turn document steps into English execute_goal steps, "
    "derive success criteria from the document, and apply user overrides. "
    "When a document step cannot be automated, include an advice step: "
    "{\"step_type\": \"advice\", \"advice\": \"<guidance or alternative>\", "
    "\"success_criteria\": \"...\"}. "
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
    "otherwise later steps may still run. "
    "Reply with JSON only: {\"workflow\": \"<type>\", \"steps\": ["
    "{\"tool_name\": \"execute_goal\", "
    "\"arguments\": {\"instruction\": \"...\"}, "
    "\"success_criteria\": \"<short done note>\", "
    "\"requires_attachment\": false}, "
    "{\"step_type\": \"advice\", \"advice\": \"...\", \"success_criteria\": \"...\"}, "
    "{\"step_type\": \"halt\", \"message\": \"...\"}]}. "
    "Keep success_criteria compact. Prefer a short string. If you emit relations, "
    "emit a small list — never a catalog of unused types. "
    "SAFETY GUARDRAILS (mandatory — never violate): "
    "NEVER plan steps that delete, remove, truncate, drop, purge, wipe, erase, "
    "destroy, unlink, or overwrite existing files, directories, blobs, uploads, "
    "attachments, or workflow-library originals. "
    "Creating or uploading new output files is allowed; deleting or replacing "
    "existing stored data is forbidden. "
    "Writing new artifacts from existing inputs is not overwrite. Return empty "
    "steps only when the user asked to delete or destroy stored data. "
    "NEVER plan database mutations that DELETE rows, DROP or TRUNCATE tables or "
    "schemas, or run destructive SQL (DELETE, DROP, TRUNCATE, ALTER ... DROP). "
    "Read-only DB access (SELECT, list, get, search) is allowed. "
    "NEVER plan shell or CLI steps whose purpose is deletion (rm, del, rmdir, "
    "unlink, shred, or equivalent). "
    "If the user asks to delete files, rows, tables, or other stored data — even "
    "in English — refuse: return "
    "{\"workflow\": \"qa\", \"steps\": []}. "
    "Prefer read-only, additive, or compose-only steps: fetch, search, list, get, "
    "download, parse, summarize, compose, create (new artifacts), upload (new files). "
    "Plan the minimum steps needed: each execute_goal should perform one distinct "
    "transformation. When a step creates a new file in the working directory, do not "
    "add a follow-up step to upload, save, or re-register that same artifact unless "
    "the user explicitly asked for a separate delivery action. Put the outcome "
    "contract in success_criteria, not in extra inspect steps. "
    "When the user attached a file and the request is a single transformation on that "
    "file (split, convert, merge, extract, export), plan one execute_goal step that "
    "delivers the outcome directly. Do not add separate validation, readability, "
    "existence-check, or inspect steps; the checker evaluates the relations."
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


def _loads_plan_json(blob: str) -> Any | None:
    """Parse one JSON value; tolerate trailing text and trailing commas."""
    text = (blob or "").strip()
    if not text:
        return None
    variants = [text, _strip_trailing_commas(text)]
    for candidate in variants:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        try:
            value, _end = json.JSONDecoder().raw_decode(candidate)
            return value
        except json.JSONDecodeError:
            continue
    return None


def _strip_trailing_commas(text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", text)


def _plan_items(parsed: Any) -> tuple[str, list[Any]]:
    """Extract workflow + step list from common planner shapes."""
    if isinstance(parsed, list):
        return "qa", parsed
    if not isinstance(parsed, dict):
        return "qa", []
    workflow = str(parsed.get("workflow") or "qa").strip() or "qa"
    for key in ("steps", "plan_steps"):
        items = parsed.get(key)
        if isinstance(items, list):
            return workflow, items
    nested = parsed.get("plan")
    if isinstance(nested, list):
        return workflow, nested
    if isinstance(nested, dict):
        items = nested.get("steps")
        if isinstance(items, list):
            nested_wf = str(nested.get("workflow") or workflow).strip() or workflow
            return nested_wf, items
    return workflow, []


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
    array_start = text.find("[")
    array_end = text.rfind("]")
    if array_start >= 0 and array_end > array_start:
        candidates.append(text[array_start : array_end + 1])
    parsed: Any = None
    for blob in candidates:
        parsed = _loads_plan_json(blob)
        if parsed is not None:
            break
    if parsed is None:
        return "qa", []
    workflow, items = _plan_items(parsed)
    if not items:
        return workflow, []
    steps: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        step_type = str(item.get("step_type") or STEP_TYPE_TOOL).strip().lower()
        criteria = item.get("success_criteria")
        if criteria is None:
            criteria = item.get("success")
        if isinstance(criteria, list):
            criteria = {"relations": criteria}
        sibling_relations = item.get("relations")
        if isinstance(sibling_relations, list):
            if isinstance(criteria, str) and criteria.strip():
                criteria = {"text": criteria, "relations": sibling_relations}
            elif isinstance(criteria, dict) and "relations" not in criteria:
                criteria = {**criteria, "relations": sibling_relations}
            elif criteria is None:
                criteria = {"relations": sibling_relations}
        preconditions = extract_preconditions(item)
        on_precondition_fail = extract_on_precondition_fail(item)
        stop_after = item.get("stop_after")
        raw_args = item.get("arguments")
        args = dict(raw_args) if isinstance(raw_args, dict) else {}
        instruction = str(
            args.get("instruction")
            or args.get("goal")
            or item.get("instruction")
            or item.get("goal")
            or ""
        ).strip()
        message_text = str(
            item.get("advice") or item.get("message") or ""
        ).strip()
        if not message_text and not instruction:
            message_text = str(item.get("text") or "").strip()
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
        named = str(item.get("tool_name") or item.get("name") or "").strip()
        if step_type == STEP_TYPE_ADVICE or (not named and message_text and not instruction):
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
        name = named
        if instruction and "instruction" not in args:
            args["instruction"] = instruction
        if criteria is not None and "success_criteria" not in args:
            # keep column value; also mirror for executor convenience
            pass
        # English goal without catalog tool id
        if not name and instruction:
            name = EXECUTE_GOAL_TOOL_NAME
        if not name:
            continue
        # Normalize legacy/catalog-looking names that carry only English goals
        if instruction and name not in {
            ADVICE_STEP_TOOL_NAME,
            HALT_STEP_TOOL_NAME,
            EXECUTE_GOAL_TOOL_NAME,
            "uvx_cli",
            "run_uvx",
        }:
            # Keep explicit non-goal tool names for injected/test tools.
            pass
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


def _explicit_empty_steps(raw: str) -> bool:
    """True when the model returned a plan object whose steps list is empty."""
    text = (raw or "").strip()
    if not text:
        return False
    parsed = _loads_plan_json(text)
    if parsed is None:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            parsed = _loads_plan_json(text[start : end + 1])
    if not isinstance(parsed, dict):
        return False
    items = parsed.get("steps", parsed.get("plan_steps"))
    return isinstance(items, list) and len(items) == 0


def _looks_like_json_plan(raw: str) -> bool:
    text = (raw or "").strip()
    if "{" in text and any(
        token in text
        for token in ("steps", "tool_name", "instruction", "workflow", "execute_goal")
    ):
        return True
    return text.startswith("[{") or text.startswith("[ {")


def recover_execute_goal_steps(
    raw: str,
    question: str,
    *,
    has_attachments: bool = False,
) -> list[dict[str, Any]]:
    """If planner JSON is unusable, the user request is still one execute_goal."""
    q = (question or "").strip()
    if not q or _explicit_empty_steps(raw):
        return []
    text = (raw or "").strip()
    empty = (not text) or text == EMPTY_COMPLETION_TEXT
    if not empty and not _looks_like_json_plan(text):
        return []
    preconditions: dict[str, Any] = {}
    if has_attachments:
        preconditions["requires_attachment"] = True
    step: dict[str, Any] = {
        "tool_name": EXECUTE_GOAL_TOOL_NAME,
        "arguments": {"instruction": q},
        "success_criteria": q,
        "step_type": STEP_TYPE_TOOL,
        "preconditions": preconditions,
    }
    if has_attachments:
        step["requires_attachment"] = True
    return [step]


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
    workflow_body_max_chars: int = 1500,
    client_id: str | None = None,
) -> str:
    parts = [
        f"User request:\n{gathered.question}",
        "Plan plain-English execute_goal steps only. "
        "Do not use a tool registry or invent CLI package names.",
    ]
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
            "Use the stored workflow document body as the source of truth. "
            "Turn each automatable document step into an execute_goal with a clear "
            "English instruction and relation-typed success_criteria. "
            "For steps that cannot be automated, add an advice step."
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
    planner_raw: str | None = None,
) -> UUID:
    source = gathered.as_source()
    if error:
        source["error"] = error
    if planner_raw:
        source["planner_raw"] = planner_raw[:8000]
    plan_json: dict[str, Any] = {"workflow": workflow, "steps": steps}
    if error:
        plan_json["error"] = error
    if planner_raw and error:
        plan_json["planner_raw"] = planner_raw[:8000]
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

        settings = extra.get("settings")
        if settings is None:
            from api.app.settings import get_settings

            settings = get_settings()
            extra = {**extra, "settings": settings}

        workflow_body_max = int(
            getattr(settings, "tool_rag_workflow_body_chars", 1500) or 1500
        )
        user_prompt = _planning_user_message(
            gathered,
            workflow_body_max_chars=workflow_body_max,
            client_id=context.client_id,
        )
        log_tool_rag_activity(
            phase="plan_context",
            client_id=context.client_id,
            shortlist_count=0,
            shortlist_names=[],
            attachment_count=len(gathered.attachments or []),
            has_workflow=gathered.workflow is not None,
            prompt_chars=len(user_prompt),
            includes_subcommands=False,
            english_goals=True,
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
        if not steps:
            recovered = recover_execute_goal_steps(
                result.text,
                context.question,
                has_attachments=bool(gathered.attachments),
            )
            if recovered:
                logger.warning(
                    "orchestrator_plan_recovered_execute_goal client_id=%s raw_chars=%s",
                    context.client_id,
                    len(result.text or ""),
                )
                steps = recovered
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
            tools_from_shortlist=False,
            english_goals=True,
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
                planner_raw=result.text,
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

"""Generic plan step types, preconditions, and runtime checks (Phase 1).

Reserved step markers (not catalog tools): ``advice``, ``halt``.
Step metadata is persisted under ``arguments["_step_meta"]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ADVICE_STEP_TOOL_NAME = "advice"
HALT_STEP_TOOL_NAME = "halt"
STEP_META_KEY = "_step_meta"

STEP_TYPE_TOOL = "tool"
STEP_TYPE_ADVICE = "advice"
STEP_TYPE_HALT = "halt"


@dataclass
class ExecutionContext:
    """Runtime facts available when executing a persisted plan."""

    attachments: list[dict[str, Any]] = field(default_factory=list)
    tenant_id: str = ""
    workflow_title: str | None = None

    @classmethod
    def from_agent_context(
        cls,
        *,
        client_id: str,
        attachments: list[dict[str, Any]] | None,
        plan_source: dict[str, Any] | None,
    ) -> ExecutionContext:
        runtime_attachments = list(attachments or [])
        if not runtime_attachments and plan_source:
            stored = plan_source.get("attachments")
            if isinstance(stored, list):
                runtime_attachments = list(stored)
        title = None
        if plan_source:
            title = plan_source.get("workflow_title")
        return cls(
            attachments=runtime_attachments,
            tenant_id=client_id,
            workflow_title=str(title) if title else None,
        )


def extract_preconditions(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize precondition fields from a planner JSON step."""
    pre = item.get("preconditions")
    out: dict[str, Any] = dict(pre) if isinstance(pre, dict) else {}
    if item.get("requires_attachment"):
        out["requires_attachment"] = True
    requires = item.get("requires")
    if isinstance(requires, list):
        out["requires"] = [str(r).strip().lower() for r in requires if str(r).strip()]
    return out


def extract_on_precondition_fail(item: dict[str, Any]) -> str | None:
    raw = item.get("on_precondition_fail")
    if isinstance(raw, dict):
        text = str(raw.get("message") or raw.get("text") or "").strip()
        return text or None
    if isinstance(raw, str):
        text = raw.strip()
        return text or None
    return None


def step_message(arguments: dict[str, Any] | None) -> str:
    args = arguments or {}
    return str(args.get("text") or args.get("message") or "").strip()


def step_meta(arguments: dict[str, Any] | None) -> dict[str, Any]:
    args = arguments or {}
    meta = args.get(STEP_META_KEY)
    return dict(meta) if isinstance(meta, dict) else {}


def infer_step_type(tool_name: str, meta: dict[str, Any]) -> str:
    explicit = str(meta.get("step_type") or "").strip().lower()
    if explicit in {STEP_TYPE_TOOL, STEP_TYPE_ADVICE, STEP_TYPE_HALT}:
        return explicit
    name = (tool_name or "").strip()
    if name == ADVICE_STEP_TOOL_NAME:
        return STEP_TYPE_ADVICE
    if name == HALT_STEP_TOOL_NAME:
        return STEP_TYPE_HALT
    return STEP_TYPE_TOOL


def tool_arguments(arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Strip executor metadata before invoking a catalog tool."""
    args = dict(arguments or {})
    args.pop(STEP_META_KEY, None)
    return args


def build_step_meta(step: dict[str, Any]) -> dict[str, Any]:
    step_type = str(step.get("step_type") or STEP_TYPE_TOOL).strip().lower()
    meta: dict[str, Any] = {"step_type": step_type}
    pre = step.get("preconditions") or {}
    if pre:
        meta["preconditions"] = dict(pre)
    fail_msg = step.get("on_precondition_fail")
    if fail_msg:
        meta["on_precondition_fail"] = fail_msg
    stop_after = step.get("stop_after")
    if stop_after is not None:
        meta["stop_after"] = bool(stop_after)
    elif step_type == STEP_TYPE_HALT:
        meta["stop_after"] = True
    return meta


def arguments_with_meta(step: dict[str, Any]) -> dict[str, Any]:
    args = dict(step.get("arguments") or {})
    meta = build_step_meta(step)
    if (
        meta["step_type"] != STEP_TYPE_TOOL
        or meta.get("preconditions")
        or meta.get("on_precondition_fail")
        or meta.get("stop_after")
    ):
        args[STEP_META_KEY] = meta
    return args


def check_preconditions(
    preconditions: dict[str, Any],
    ctx: ExecutionContext,
) -> tuple[bool, str]:
    """Return (ok, reason). Generic checks only — no workflow-specific logic."""
    if not preconditions:
        return True, ""
    if preconditions.get("requires_attachment") and not ctx.attachments:
        return False, "required attachment is missing"
    requires = preconditions.get("requires")
    if isinstance(requires, list):
        needs_file = any(r in {"attachment", "file", "upload"} for r in requires)
        if needs_file and not ctx.attachments:
            return False, "required attachment is missing"
    return True, ""


def precondition_fail_message(meta: dict[str, Any], reason: str) -> str:
    custom = meta.get("on_precondition_fail")
    if isinstance(custom, str) and custom.strip():
        return custom.strip()
    return reason or "precondition not met"

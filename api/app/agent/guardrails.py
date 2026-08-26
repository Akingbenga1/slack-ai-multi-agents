"""Agent guardrails — hedge without evidence; never drop tenant filter (13.4)."""

from __future__ import annotations

import json
import re
from typing import Any

from api.app.tenant import ClientIdRequired
from api.app.tenant import require_client_id as _require_client_id

PLAN_SAFETY_REFUSAL = (
    "Plan rejected: destructive operations (file deletion or database row/table "
    "deletion) are not permitted."
)

_DESTRUCTIVE_TOOL_RE = re.compile(
    r"(^|[_.-])("
    r"delete|remove|drop|truncate|purge|wipe|erase|destroy|unlink|shred|obliterate"
    r")([_.-]|$)",
    re.I,
)

_DESTRUCTIVE_TOKEN_RE = re.compile(
    r"\b("
    r"delete|remove|drop|truncate|purge|wipe|erase|destroy|unlink|shred|obliterate"
    r")\b",
    re.I,
)

_DESTRUCTIVE_SQL_RE = re.compile(
    r"\b("
    r"DELETE\s+FROM|DROP\s+(TABLE|DATABASE|SCHEMA|INDEX|VIEW)|"
    r"TRUNCATE\s+(TABLE\s+)?|ALTER\s+TABLE\s+.+?\s+DROP"
    r")\b",
    re.I,
)

_DESTRUCTIVE_CLI_RE = re.compile(
    r"(?<![\w./])(rm\s+-|rm\s+\S|del\s+/|rmdir\b|unlink\b|shred\b)",
    re.I,
)

HEDGE_MESSAGE = (
    "I don't have enough information in your organisation's knowledge base "
    "to answer that confidently. Try rephrasing, or sync Slack history / "
    "upload documents that cover this topic."
)


class TenantContextRequired(ClientIdRequired):
    """Raised when agent state is missing a usable client_id."""


def require_tenant_client_id(client_id: str | None, *, where: str = "agent") -> str:
    """Fail-closed: every agent node must carry a non-empty tenant id."""
    try:
        return _require_client_id(client_id, where=where)
    except ClientIdRequired as exc:
        if isinstance(exc, TenantContextRequired):
            raise
        raise TenantContextRequired(
            f"client_id is required for {where} (tenant filter must never be dropped)"
        ) from exc


def filter_chunks_for_tenant(
    chunks: list[dict[str, Any]] | None,
    client_id: str,
    *,
    min_score: float | None = None,
) -> list[dict[str, Any]]:
    """Keep only tenant-matching chunks; optionally drop weak scores."""
    cid = require_tenant_client_id(client_id, where="filter_chunks_for_tenant")
    out: list[dict[str, Any]] = []
    for chunk in chunks or []:
        if not isinstance(chunk, dict):
            continue
        if (chunk.get("client_id") or "").strip() != cid:
            continue
        if min_score is not None:
            try:
                score = float(chunk.get("score") or 0.0)
            except (TypeError, ValueError):
                score = 0.0
            if score < float(min_score):
                continue
        out.append(chunk)
    return out


def should_hedge(chunks: list[dict[str, Any]] | None) -> bool:
    """True when there is no tenant-scoped retrieval evidence."""
    return not bool(chunks)


def _step_text(step: dict[str, Any]) -> str:
    """Flatten a plan step for destructive-pattern scanning."""
    parts = [str(step.get("tool_name") or "")]
    args = step.get("arguments")
    if isinstance(args, dict):
        parts.append(json.dumps(args, default=str))
        subcommand = args.get("subcommand")
        if subcommand:
            parts.append(str(subcommand))
        args_list = args.get("args_list")
        if isinstance(args_list, list):
            parts.extend(str(item) for item in args_list)
    elif args is not None:
        parts.append(str(args))
    criteria = step.get("success_criteria")
    if criteria is not None:
        parts.append(str(criteria))
    return " ".join(parts)


def find_destructive_plan_violations(
    steps: list[dict[str, Any]] | None,
) -> list[str]:
    """Return human-readable violations when a plan includes destructive work."""
    violations: list[str] = []
    for index, step in enumerate(steps or []):
        if not isinstance(step, dict):
            continue
        tool_name = str(step.get("tool_name") or "").strip()
        blob = _step_text(step)
        if tool_name and _DESTRUCTIVE_TOOL_RE.search(tool_name):
            violations.append(
                f"step {index}: tool_name {tool_name!r} looks destructive"
            )
        if _DESTRUCTIVE_SQL_RE.search(blob):
            violations.append(
                f"step {index}: arguments contain destructive SQL"
            )
        if _DESTRUCTIVE_CLI_RE.search(blob):
            violations.append(
                f"step {index}: arguments contain destructive shell/file commands"
            )
        subcommand = ""
        args = step.get("arguments")
        if isinstance(args, dict):
            subcommand = str(args.get("subcommand") or "").strip()
        if subcommand and _DESTRUCTIVE_TOKEN_RE.search(subcommand):
            violations.append(
                f"step {index}: subcommand {subcommand!r} looks destructive"
            )
    return violations

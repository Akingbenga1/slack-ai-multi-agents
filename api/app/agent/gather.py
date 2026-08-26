"""Read-only context gather for the orchestrator (Sprint 44.1).

Loads attachment metadata and tenant-scoped ``workflow_templates``. Never
posts to Slack, never mutates the library, never downloads or parses files
as a deliverable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.db.models import WorkflowTemplate
from api.app.workflows.library import get_template, list_templates

ChannelLookup = Callable[[str], str | None]

_CHANNEL_RE = re.compile(r"#[A-Za-z0-9_-]+")
_NAMED_WORKFLOW_RE = re.compile(
    r"\bthe\s+((?:(?!\bworkflow\b).)+?)\s+workflow\b",
    re.I,
)
_RUN_WORKFLOW_RE = re.compile(
    r"(\b(run|execute|start)\b.+\bworkflow\b)"
    r"|(\bworkflow\b.+\b(run|execute)\b)"
    r"|(\bget me the workflow\b)"
    r"|(\bworkflow i (defined|stored)\b)",
    re.I,
)
_STORE_ONLY_RE = re.compile(
    r"\bstore\b.+\bworkflow\b",
    re.I,
)
_YESTERDAY_RE = re.compile(r"\byesterday\b", re.I)
_META_KEYS_SKIP = frozenset(
    {
        "text",
        "bytes",
        "data",
        "content",
        "body",
        "body_text",
        "parsed",
        "url_private_download",
    }
)


@dataclass
class GatheredContext:
    """Read-only facts the planner may use. No work-tool results."""

    question: str
    attachments: list[dict[str, Any]] = field(default_factory=list)
    wants_stored_workflow: bool = False
    workflow: dict[str, Any] | None = None
    workflow_error: str | None = None
    channel_names: list[str] = field(default_factory=list)
    channels: dict[str, str] = field(default_factory=dict)

    def as_source(self) -> dict[str, Any]:
        """JSON-safe gather snapshot stored on ``agent_plans.source``."""
        payload: dict[str, Any] = {
            "attachments": list(self.attachments),
            "wants_stored_workflow": self.wants_stored_workflow,
            "channel_names": list(self.channel_names),
            "channels": dict(self.channels),
        }
        if self.workflow is not None:
            payload["workflow_template_id"] = self.workflow.get("id")
            payload["workflow_title"] = self.workflow.get("title")
            payload["workflow_body"] = self.workflow.get("body_text")
        if self.workflow_error:
            payload["gather_error"] = self.workflow_error
        return payload


def attachment_metadata(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Keep filename / type / ids / storage path. Drop parsed bytes/text."""
    item = raw or {}
    filename = (
        str(item.get("filename") or item.get("name") or "").strip() or None
    )
    file_type = (
        str(
            item.get("mimetype")
            or item.get("content_type")
            or item.get("filetype")
            or item.get("type")
            or ""
        ).strip()
        or None
    )
    file_id = str(
        item.get("slack_file_id") or item.get("file_id") or ""
    ).strip()
    if not file_id:
        raw_id = str(item.get("id") or "").strip()
        if raw_id.startswith("F"):
            file_id = raw_id
    storage_rel = str(
        item.get("storage_relative_path") or item.get("relative_path") or ""
    ).strip()
    local_path = str(
        item.get("local_path") or item.get("absolute_path") or ""
    ).strip()
    upload_id = str(item.get("upload_id") or "").strip()
    meta: dict[str, Any] = {}
    if filename:
        meta["filename"] = filename
    if file_type and file_type not in _META_KEYS_SKIP:
        meta["type"] = file_type
    if file_id:
        meta["slack_file_id"] = file_id
    if upload_id:
        meta["upload_id"] = upload_id
    if storage_rel:
        meta["storage_relative_path"] = storage_rel
    if local_path:
        meta["local_path"] = local_path
    return meta


def wants_stored_workflow(question: str) -> bool:
    """True when the user asks to run a library document, not to store one."""
    text = (question or "").strip()
    if not text:
        return False
    if _STORE_ONLY_RE.search(text) and not _RUN_WORKFLOW_RE.search(text):
        return False
    return bool(_RUN_WORKFLOW_RE.search(text))


def extract_workflow_title(question: str) -> str | None:
    match = _NAMED_WORKFLOW_RE.search(question or "")
    if not match:
        return None
    title = re.sub(r"\s+", " ", match.group(1)).strip()
    if not title or title.lower() in {"stored", "named", "shared", "defined"}:
        return None
    return title[:255]


def mentions_yesterday(question: str) -> bool:
    return bool(_YESTERDAY_RE.search(question or ""))


def extract_channel_names(question: str) -> list[str]:
    return _CHANNEL_RE.findall(question or "")


def _as_utc_date(value: datetime | None) -> date | None:
    if value is None:
        return None
    ts = value
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).date()


def _row_to_workflow(row: WorkflowTemplate) -> dict[str, Any]:
    created = row.created_at.isoformat() if row.created_at else None
    return {
        "id": str(row.id),
        "title": row.title,
        "body_text": row.body_text or "",
        "created_at": created,
        "owner_slack_user_id": row.owner_slack_user_id,
    }


def load_stored_workflow(
    db: Session,
    *,
    client_id: str,
    question: str,
    template_id: UUID | str | None = None,
    slack_user_id: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Tenant-scoped library read. Returns (workflow, error)."""
    if template_id:
        try:
            row = get_template(db, client_id=client_id, template_id=template_id)
        except LookupError:
            return None, "No stored workflow matched this request."
        return _row_to_workflow(row), None

    title = extract_workflow_title(question)
    rows = list_templates(
        db,
        client_id=client_id,
        q=title,
        include_personal_for=slack_user_id,
        limit=50,
    )
    if mentions_yesterday(question):
        target = datetime.now(timezone.utc).date() - timedelta(days=1)
        rows = [r for r in rows if _as_utc_date(r.created_at) == target]
    if not rows:
        return None, "No stored workflow matched this request."
    return _row_to_workflow(rows[0]), None


def gather(
    context_question: str,
    *,
    client_id: str,
    attachments: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
    db: Session | None = None,
    channel_lookup: Optional[ChannelLookup] = None,
) -> GatheredContext:
    """Collect read-only planning context. Does not write plans or run tools."""
    extra = extra or {}
    question = context_question or ""
    meta = [attachment_metadata(a) for a in (attachments or []) if a]
    meta = [m for m in meta if m]
    names = extract_channel_names(question)
    resolved: dict[str, str] = {}
    lookup = channel_lookup or extra.get("channel_lookup")
    if callable(lookup):
        for name in names:
            cid = lookup(name)
            if cid:
                resolved[name] = str(cid)

    gathered = GatheredContext(
        question=question,
        attachments=meta,
        wants_stored_workflow=wants_stored_workflow(question),
        channel_names=names,
        channels=resolved,
    )
    explicit_id = extra.get("template_id") or extra.get("workflow_template_id")
    if not gathered.wants_stored_workflow and not explicit_id:
        return gathered
    if db is None:
        gathered.workflow_error = "No stored workflow matched this request."
        gathered.wants_stored_workflow = True
        return gathered
    owner = str(extra.get("slack_user_id") or extra.get("owner_slack_user_id") or "")
    workflow, err = load_stored_workflow(
        db,
        client_id=client_id,
        question=question,
        template_id=explicit_id,
        slack_user_id=owner or None,
    )
    gathered.wants_stored_workflow = True
    gathered.workflow = workflow
    gathered.workflow_error = err
    return gathered

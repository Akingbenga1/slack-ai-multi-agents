"""Delivery — post agent answer to Slack (Sprint 26.2).

Slack delivery only formats and posts the agent result. Side effects
(store/list/copy/edit, PDF upload, rename) belong to agent tools, not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.governance.usage import EVENT_SLACK_MENTION, record_usage
from api.app.logging_config import get_logger
from api.app.settings import Settings
from api.app.slack.formatting import format_slack_reply

logger = get_logger("api.slack.delivery")

PostFn = Callable[..., dict[str, Any]]


@dataclass
class DeliveryContext:
    """Mutable bag for one mention/DM delivery after Gate / Intake / RunAgent."""

    db: Session
    tenant_id: UUID
    bot_token: str
    channel: str
    thread_ts: str | None
    question: str
    conversation_id: str
    event: dict[str, Any]
    team_id: str | None
    settings: Settings
    upload_root: Path
    db_factory: Callable[[], Session]
    post: PostFn
    attached_payload: list[dict[str, Any]] = field(default_factory=list)
    intake_errors: list[str] = field(default_factory=list)
    slack_user: str | None = None
    agent_result: dict[str, Any] | None = None
    workflow: str | None = None
    answer: str = ""


class DeliveryStrategy(Protocol):
    """Strategy contract: post the agent reply to Slack."""

    def deliver(self, ctx: DeliveryContext) -> dict[str, Any]:
        """Post; return process_agent_reply result dict."""


def _post_formatted(ctx: DeliveryContext, *, hedge: bool, chunks: Any = None) -> None:
    text = format_slack_reply(ctx.answer, chunks=chunks, hedge=hedge)
    ctx.post(
        bot_token=ctx.bot_token,
        channel=ctx.channel,
        text=text,
        thread_ts=ctx.thread_ts,
    )


def _record_mention(
    ctx: DeliveryContext,
    *,
    workflow: str,
    hedge: bool = False,
    extra_meta: dict[str, Any] | None = None,
) -> None:
    result = ctx.agent_result or {}
    meta: dict[str, Any] = {
        "event_type": ctx.event.get("type"),
        "channel": ctx.channel,
        "team_id": ctx.team_id,
        "workflow": workflow,
        "hedge": hedge,
        "usage_tokens": int(result.get("usage_tokens") or 0),
        "attachments": len(ctx.attached_payload),
        "intake_errors": ctx.intake_errors[:3],
    }
    if extra_meta:
        meta.update(extra_meta)
    record_usage(
        ctx.db,
        ctx.tenant_id,
        EVENT_SLACK_MENTION,
        units=1,
        meta=meta,
        commit=True,
    )


class DefaultPostStrategy:
    """Format answer + ``chat.postMessage``."""

    def deliver(self, ctx: DeliveryContext) -> dict[str, Any]:
        result = ctx.agent_result or {}
        workflow = str(ctx.workflow or result.get("workflow") or "qa")
        ctx.answer = str(result.get("answer") or ctx.answer or "")

        _post_formatted(
            ctx,
            hedge=bool(result.get("hedge")),
            chunks=result.get("retrieved_chunks"),
        )
        _record_mention(ctx, workflow=workflow, hedge=bool(result.get("hedge")))
        logger.info(
            "slack_agent_reply_ok tenant_id=%s channel=%s workflow=%s hedge=%s "
            "chunks=%s attachments=%s",
            ctx.tenant_id,
            ctx.channel,
            workflow,
            result.get("hedge"),
            len(result.get("retrieved_chunks") or []),
            len(ctx.attached_payload),
        )
        return {
            "ok": True,
            "denied": False,
            "answer": ctx.answer,
            "hedge": bool(result.get("hedge")),
            "workflow": workflow,
            "attachments": len(ctx.attached_payload),
        }


_DEFAULT = DefaultPostStrategy()


def get_delivery_strategy(workflow: str | None = None) -> DeliveryStrategy:
    """Always post via DefaultPostStrategy; workflow is informational only."""
    _ = workflow
    return _DEFAULT


def resolve_delivery_strategy(workflow: str | None = None) -> DeliveryStrategy:
    """Public alias matching historical name."""
    return get_delivery_strategy(workflow)


__all__ = [
    "DefaultPostStrategy",
    "DeliveryContext",
    "DeliveryStrategy",
    "get_delivery_strategy",
    "resolve_delivery_strategy",
]

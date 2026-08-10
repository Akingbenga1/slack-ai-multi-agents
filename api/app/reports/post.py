"""Generate + post a recurring report to Slack (Sprint 17.3)."""

from __future__ import annotations

from typing import Any, Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.agent.run import run_report
from api.app.logging_config import get_logger
from api.app.reports.schedule import get_recurring_report_schedule
from api.app.settings import Settings, get_settings
from api.app.slack.echo import post_message
from api.app.slack.formatting import format_slack_reply
from api.app.slack.store import get_bot_token, get_install_by_tenant
from api.app.slack.sync import sync_slack_history

logger = get_logger("api.reports.post")

PostMessageFn = Callable[..., dict[str, Any]]
RunReportFn = Callable[..., dict[str, Any]]
SyncFn = Callable[..., Any]


def post_recurring_report(
    db: Session,
    *,
    tenant_id: UUID | str,
    channel_id: str | None = None,
    window_label: str | None = None,
    prefer_sync: bool = True,
    settings: Settings | None = None,
    run_report_fn: RunReportFn | None = None,
    post_message_fn: PostMessageFn | None = None,
    sync_fn: SyncFn | None = None,
    record_usage: bool = True,
) -> dict[str, Any]:
    """
    Prefer a fresh channel sync, generate the digest, post **directly** to the
    channel (no draft-approval gate, no thread).

    Returns a result dict for job metadata. Raises on hard failures (no install,
    no channel, Slack post not ok).
    """
    settings = settings or get_settings()
    tid = UUID(str(tenant_id))
    sched = get_recurring_report_schedule(db, tid)
    channel = (channel_id or sched.get("channel_id") or "").strip()
    if not channel:
        raise ValueError("recurring report channel_id is required")
    window = (window_label or sched.get("window_label") or "last 7 days").strip()

    install = get_install_by_tenant(db, tid)
    if install is None:
        raise RuntimeError("Slack is not connected for this tenant")
    bot_token = get_bot_token(install, settings)
    if not bot_token:
        raise RuntimeError("Slack bot token missing for this tenant")

    sync_meta: dict[str, Any] = {"attempted": False, "ok": False}
    if prefer_sync:
        sync_meta["attempted"] = True
        try:
            sync = sync_fn or sync_slack_history
            sync_result = sync(
                db,
                tenant_id=tid,
                channel_ids=[channel],
                settings=settings,
            )
            sync_meta["ok"] = True
            as_dict = getattr(sync_result, "as_dict", None)
            if callable(as_dict):
                sync_meta["result"] = as_dict()
            logger.info(
                "recurring_report_sync_ok client_id=%s channel=%s",
                tid,
                channel,
            )
        except Exception as exc:
            # Prefer freshness but do not block the digest on sync failure.
            sync_meta["ok"] = False
            sync_meta["error"] = str(exc)[:500]
            logger.warning(
                "recurring_report_sync_failed client_id=%s channel=%s err=%s",
                tid,
                channel,
                exc,
            )

    runner = run_report_fn or run_report
    report = runner(
        client_id=str(tid),
        window_label=window,
        channel=channel,
        record_usage=record_usage,
        settings=settings,
    )
    text = format_slack_reply(
        str(report.get("answer") or ""),
        chunks=report.get("retrieved_chunks"),
        hedge=bool(report.get("hedge")),
    )

    post = post_message_fn or post_message
    # Direct channel post — top-level (no thread_ts), no approval gate.
    slack_resp = post(
        bot_token=bot_token,
        channel=channel,
        text=text,
        thread_ts=None,
    )
    if not slack_resp.get("ok"):
        err = slack_resp.get("error") or "chat.postMessage failed"
        raise RuntimeError(f"Slack post failed: {err}")

    logger.info(
        "recurring_report_posted client_id=%s channel=%s hedge=%s ts=%s",
        tid,
        channel,
        report.get("hedge"),
        slack_resp.get("ts"),
    )
    return {
        "client_id": str(tid),
        "channel_id": channel,
        "window_label": window,
        "cadence": sched.get("cadence"),
        "workflow": "report",
        "hedge": bool(report.get("hedge")),
        "usage_tokens": int(report.get("usage_tokens") or 0),
        "slack_ts": slack_resp.get("ts"),
        "sync": sync_meta,
        "answer_preview": text[:240],
    }


__all__ = ["post_recurring_report"]

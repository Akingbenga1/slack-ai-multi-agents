"""Mention/DM reply pipeline stages — Gate → Intake → RunAgent → Deliver.

Sprint 26.1: orchestration only. Delivery side effects live in
``api.app.slack.delivery`` Strategies (26.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.agent.run import run_agent
from api.app.agent.state import FILE_HEAVY_WORKFLOWS
from api.app.agent.workflows import classify_workflow
from api.app.governance.usage import EVENT_FILE_JOB, record_usage
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings
from api.app.slack.delivery import DeliveryContext, get_delivery_strategy
from api.app.slack.echo import (
    conversation_id_for_event,
    post_message,
    question_from_event,
    reply_thread_ts,
)
from api.app.slack.files import files_from_event, intake_attachments
from api.app.slack.workflow_actions import (
    MSG_ADVICE_NO_EVIDENCE,
    enrich_evidence_for_advice,
)
from api.app.tenant import set_client_id

logger = get_logger("api.slack.reply_pipeline")

PostFn = Callable[..., dict[str, Any]]
RunAgentFn = Callable[..., dict[str, Any]]
DbFactory = Callable[[], Session]


@dataclass
class ReplyPipelineContext:
    """Accumulated state across Gate → Intake → RunAgent → Deliver."""

    tenant_id: UUID
    bot_token: str
    event: dict[str, Any]
    team_id: str | None
    settings: Settings
    db_factory: DbFactory
    invoke: RunAgentFn
    post: PostFn
    channel: str
    question: str
    conversation_id: str
    thread_ts: str | None
    pre_workflow: str
    has_file_refs: bool
    db: Session | None = None
    upload_root: Path | None = None
    attached_payload: list[dict[str, Any]] = field(default_factory=list)
    intake_errors: list[str] = field(default_factory=list)
    slack_user: str | None = None
    agent_result: dict[str, Any] | None = None
    answer: str = ""
    early_return: dict[str, Any] | None = None
    skip_agent: bool = False


def stage_gate(
    ctx: ReplyPipelineContext,
    *,
    check_agent_entitlement: Callable[..., tuple[bool, str]],
    check_file_job_entitlement: Callable[..., tuple[bool, str]],
) -> ReplyPipelineContext:
    """Entitlement / jobs_daily gate; denial posts and early-return."""
    assert ctx.db is not None
    allowed, denial = check_agent_entitlement(ctx.db, ctx.tenant_id)
    if not allowed:
        logger.info(
            "slack_agent_denied tenant_id=%s reason=%s",
            ctx.tenant_id,
            denial[:80],
        )
        ctx.post(
            bot_token=ctx.bot_token,
            channel=ctx.channel,
            text=denial,
            thread_ts=ctx.thread_ts,
        )
        ctx.early_return = {"ok": True, "denied": True, "reason": denial}
        return ctx

    if ctx.pre_workflow in FILE_HEAVY_WORKFLOWS:
        ok_job, job_denial = check_file_job_entitlement(ctx.db, ctx.tenant_id)
        if not ok_job:
            logger.info(
                "slack_file_job_denied tenant_id=%s workflow=%s",
                ctx.tenant_id,
                ctx.pre_workflow,
            )
            ctx.post(
                bot_token=ctx.bot_token,
                channel=ctx.channel,
                text=job_denial,
                thread_ts=ctx.thread_ts,
            )
            ctx.early_return = {
                "ok": True,
                "denied": True,
                "reason": job_denial,
                "workflow": ctx.pre_workflow,
            }
    return ctx


def stage_intake(ctx: ReplyPipelineContext) -> ReplyPipelineContext:
    """Attachment Strategy: none vs parse evidence."""
    assert ctx.db is not None
    assert ctx.upload_root is not None
    ctx.slack_user = str(ctx.event.get("user") or "").strip() or None
    if not ctx.has_file_refs:
        return ctx

    intake = intake_attachments(
        client_id=str(ctx.tenant_id),
        bot_token=ctx.bot_token,
        event=ctx.event,
        upload_root=ctx.upload_root,
    )
    ctx.attached_payload = [e.to_dict() for e in intake.evidence]
    ctx.intake_errors = list(intake.errors)
    record_usage(
        ctx.db,
        ctx.tenant_id,
        EVENT_FILE_JOB,
        units=1,
        meta={
            "refs": len(intake.refs),
            "parsed": len([e for e in intake.evidence if (e.text or "").strip()]),
            "errors": ctx.intake_errors[:5],
        },
        commit=True,
    )
    return ctx


def stage_run_agent(ctx: ReplyPipelineContext) -> ReplyPipelineContext:
    """Invoke ``run_agent`` (or skip for library_confirm; enrich for advise)."""
    assert ctx.db is not None
    meta = None
    try:
        from api.app.agent.workflows.registry import get_workflow_meta

        meta = get_workflow_meta(ctx.pre_workflow)
    except Exception:
        meta = None

    if meta is not None and meta.delivery_hint == "library_confirm":
        ctx.skip_agent = True
        return ctx

    if ctx.pre_workflow == "workflow_advise":
        enriched = enrich_evidence_for_advice(
            db=ctx.db,
            client_id=str(ctx.tenant_id),
            question=ctx.question,
            attached_evidence=ctx.attached_payload,
            slack_user_id=ctx.slack_user,
        )
        if not enriched.get("ok"):
            ctx.answer = str(enriched.get("confirmation") or MSG_ADVICE_NO_EVIDENCE)
            ctx.skip_agent = True
            return ctx
        ctx.attached_payload = list(enriched.get("evidence") or ctx.attached_payload)

    ctx.agent_result = ctx.invoke(
        client_id=str(ctx.tenant_id),
        question=ctx.question,
        conversation_id=ctx.conversation_id,
        settings=ctx.settings,
        db_factory=ctx.db_factory,
        record_usage=True,
        attached_evidence=ctx.attached_payload,
    )
    return ctx


def stage_deliver(ctx: ReplyPipelineContext) -> dict[str, Any]:
    """Dispatch DeliveryStrategy keyed by workflow / result flags."""
    assert ctx.db is not None
    assert ctx.upload_root is not None

    workflow = ctx.pre_workflow
    if ctx.agent_result:
        workflow = str(ctx.agent_result.get("workflow") or ctx.pre_workflow)

    delivery_ctx = DeliveryContext(
        db=ctx.db,
        tenant_id=ctx.tenant_id,
        bot_token=ctx.bot_token,
        channel=ctx.channel,
        thread_ts=ctx.thread_ts,
        question=ctx.question,
        conversation_id=ctx.conversation_id,
        event=ctx.event,
        team_id=ctx.team_id,
        settings=ctx.settings,
        upload_root=ctx.upload_root,
        db_factory=ctx.db_factory,
        post=ctx.post,
        invoke=ctx.invoke,
        pre_workflow=ctx.pre_workflow,
        attached_payload=ctx.attached_payload,
        intake_errors=ctx.intake_errors,
        slack_user=ctx.slack_user,
        agent_result=ctx.agent_result,
        workflow=workflow,
        answer=ctx.answer,
    )
    strategy = get_delivery_strategy(workflow)
    # Library paths key off pre_workflow even if unused agent_result
    if ctx.skip_agent and ctx.pre_workflow.startswith("workflow_"):
        strategy = get_delivery_strategy(ctx.pre_workflow)
    return strategy.deliver(delivery_ctx)


def run_reply_pipeline(
    *,
    tenant_id: UUID | str,
    bot_token: str,
    event: dict[str, Any],
    team_id: str | None = None,
    settings: Settings | None = None,
    db_factory: Optional[DbFactory] = None,
    run_agent_fn: Optional[RunAgentFn] = None,
    post_fn: Optional[PostFn] = None,
    check_agent_entitlement: Callable[..., tuple[bool, str]],
    check_file_job_entitlement: Callable[..., tuple[bool, str]],
    session_factory: Optional[DbFactory] = None,
) -> dict[str, Any]:
    """
    Gate → Intake → RunAgent → Deliver.

    Designed to run in a FastAPI BackgroundTask with a fresh DB session.
    """
    from api.app.db.session import SessionLocal

    settings = settings or get_settings()
    factory = db_factory or session_factory or SessionLocal
    invoke = run_agent_fn or run_agent
    post = post_fn or post_message

    channel = event.get("channel")
    if not channel:
        return {"ok": False, "reason": "no_channel"}

    question = question_from_event(event)
    conversation_id = conversation_id_for_event(event)
    thread_ts = reply_thread_ts(event)
    tid = UUID(str(tenant_id))
    set_client_id(str(tid))

    has_file_refs = bool(files_from_event(event))
    pre_workflow = classify_workflow(question, has_attachments=has_file_refs)

    ctx = ReplyPipelineContext(
        tenant_id=tid,
        bot_token=bot_token,
        event=event,
        team_id=team_id,
        settings=settings,
        db_factory=factory,
        invoke=invoke,
        post=post,
        channel=str(channel),
        question=question,
        conversation_id=conversation_id,
        thread_ts=thread_ts,
        pre_workflow=pre_workflow,
        has_file_refs=has_file_refs,
        upload_root=Path(settings.upload_dir),
    )

    db = factory()
    ctx.db = db
    try:
        stage_gate(
            ctx,
            check_agent_entitlement=check_agent_entitlement,
            check_file_job_entitlement=check_file_job_entitlement,
        )
        if ctx.early_return is not None:
            return ctx.early_return

        stage_intake(ctx)
        stage_run_agent(ctx)
        return stage_deliver(ctx)
    except Exception:
        logger.exception("slack_agent_reply_failed tenant_id=%s", tid)
        try:
            post(
                bot_token=bot_token,
                channel=channel,
                text=(
                    "Sorry — I hit an error answering that. "
                    "Please try again in a moment."
                ),
                thread_ts=thread_ts,
            )
        except Exception:
            logger.exception("slack_agent_error_post_failed tenant_id=%s", tid)
        return {"ok": False, "reason": "error"}
    finally:
        db.close()

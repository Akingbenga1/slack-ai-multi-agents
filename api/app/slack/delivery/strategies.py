"""DeliveryStrategy map — post-agent Slack side effects (Sprint 26.2).

How to add a delivery path:
1. Implement ``DeliveryStrategy.deliver(ctx)``.
2. Register under the workflow name (and/or wire ``resolve_delivery_strategy``).
3. Keep ``WorkflowMeta.delivery_hint`` in sync (see ``agent.workflows.registry``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.agent.workflows import question_requests_workflow_advice
from api.app.agent.workflows.registry import get_workflow_meta
from api.app.governance.usage import (
    EVENT_FILE_RENAME,
    EVENT_PDF_GENERATE,
    EVENT_SLACK_MENTION,
    EVENT_WORKFLOW_COPY,
    EVENT_WORKFLOW_STORE,
    record_usage,
)
from api.app.logging_config import get_logger
from api.app.settings import Settings
from api.app.slack.files import (
    MSG_PDF_NO_ATTACHMENT,
    evidence_has_usable_text,
    produce_and_upload_analysis_pdf,
    question_requests_rename,
    rename_slack_file_or_copy,
)
from api.app.slack.formatting import format_slack_reply
from api.app.slack.workflow_actions import (
    MSG_ADVICE_HEADER,
    MSG_ADVICE_NO_EVIDENCE,
    copy_workflow_for_slack,
    edit_workflow_draft_for_slack,
    enrich_evidence_for_advice,
    list_workflows_for_slack,
    store_workflow_from_slack,
)

logger = get_logger("api.slack.delivery")

PostFn = Callable[..., dict[str, Any]]
RunAgentFn = Callable[..., dict[str, Any]]


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
    invoke: RunAgentFn
    pre_workflow: str
    attached_payload: list[dict[str, Any]] = field(default_factory=list)
    intake_errors: list[str] = field(default_factory=list)
    slack_user: str | None = None
    # Populated by RunAgent for compose paths
    agent_result: dict[str, Any] | None = None
    workflow: str | None = None
    answer: str = ""
    file_action: dict[str, Any] | None = None
    rename_action: dict[str, Any] | None = None
    workflow_action: dict[str, Any] | None = None
    combined_advice: dict[str, Any] | None = None


class DeliveryStrategy(Protocol):
    """Strategy contract: Slack side effects + confirmation post."""

    def deliver(self, ctx: DeliveryContext) -> dict[str, Any]:
        """Post (and optional file I/O); return process_agent_reply result dict."""


def _sync_evidence_after_rename(
    attached_payload: list[dict[str, Any]],
    *,
    tenant_id: str,
    rename_action: dict[str, Any],
) -> None:
    new_rel = rename_action.get("stored_relative_path")
    new_name = rename_action.get("new_filename")
    if not new_rel or not attached_payload:
        return
    for item in attached_payload:
        if isinstance(item, dict) and item.get("client_id") == tenant_id:
            item["stored_relative_path"] = new_rel
            if new_name:
                item["filename"] = new_name
            break


def _apply_rename(ctx: DeliveryContext) -> None:
    rename_action = rename_slack_file_or_copy(
        client_id=str(ctx.tenant_id),
        upload_root=ctx.upload_root,
        question=ctx.question,
        attached_evidence=ctx.attached_payload,
        bot_token=ctx.bot_token,
    )
    ctx.rename_action = rename_action
    _sync_evidence_after_rename(
        ctx.attached_payload,
        tenant_id=str(ctx.tenant_id),
        rename_action=rename_action,
    )
    rename_note = str(rename_action.get("confirmation") or "")
    if rename_note:
        ctx.answer = (
            f"{ctx.answer}\n\n{rename_note}".strip() if ctx.answer else rename_note
        )
    record_usage(
        ctx.db,
        ctx.tenant_id,
        EVENT_FILE_RENAME,
        units=1,
        meta={
            "ok": bool(rename_action.get("ok")),
            "mode": rename_action.get("mode"),
            "new_filename": rename_action.get("new_filename"),
            "error": rename_action.get("error") or rename_action.get("slack_error"),
        },
        commit=True,
    )


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
        "pdf_ok": (ctx.file_action or {}).get("ok"),
        "rename_ok": (ctx.rename_action or {}).get("ok"),
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
        workflow = str(ctx.workflow or result.get("workflow") or ctx.pre_workflow)
        ctx.answer = str(result.get("answer") or ctx.answer or "")

        _post_formatted(
            ctx,
            hedge=bool(result.get("hedge")),
            chunks=result.get("retrieved_chunks"),
        )
        _record_mention(ctx, workflow=workflow, hedge=bool(result.get("hedge")))
        logger.info(
            "slack_agent_reply_ok tenant_id=%s channel=%s workflow=%s hedge=%s "
            "chunks=%s attachments=%s rename=%s",
            ctx.tenant_id,
            ctx.channel,
            workflow,
            result.get("hedge"),
            len(result.get("retrieved_chunks") or []),
            len(ctx.attached_payload),
            (ctx.rename_action or {}).get("ok"),
        )
        return {
            "ok": True,
            "denied": False,
            "answer": ctx.answer,
            "hedge": bool(result.get("hedge")),
            "workflow": workflow,
            "attachments": len(ctx.attached_payload),
            "file_action": ctx.file_action,
            "rename_action": ctx.rename_action,
        }


class PdfUploadStrategy:
    """PDF upload (+ optional J10 combined rename) then formatted post."""

    def deliver(self, ctx: DeliveryContext) -> dict[str, Any]:
        result = ctx.agent_result or {}
        workflow = str(result.get("workflow") or ctx.pre_workflow)
        ctx.workflow = workflow
        ctx.answer = str(result.get("answer") or "")

        if not bool(result.get("hedge")):
            if not evidence_has_usable_text(ctx.attached_payload):
                ctx.answer = (
                    f"{ctx.answer}\n\n{MSG_PDF_NO_ATTACHMENT}".strip()
                    if ctx.answer
                    else MSG_PDF_NO_ATTACHMENT
                )
            else:
                used_rag = any(
                    (c.get("kind") or "") != "attachment"
                    for c in (result.get("retrieved_chunks") or [])
                    if isinstance(c, dict)
                )
                file_action = produce_and_upload_analysis_pdf(
                    client_id=str(ctx.tenant_id),
                    bot_token=ctx.bot_token,
                    channel=str(ctx.channel),
                    analysis_text=ctx.answer,
                    attached_evidence=ctx.attached_payload,
                    upload_root=ctx.upload_root,
                    thread_ts=ctx.thread_ts,
                    title="Competitor analysis",
                    used_rag=used_rag,
                )
                ctx.file_action = file_action
                confirmation = str(file_action.get("confirmation") or "")
                if confirmation:
                    ctx.answer = f"{ctx.answer}\n\n{confirmation}".strip()
                record_usage(
                    ctx.db,
                    ctx.tenant_id,
                    EVENT_PDF_GENERATE,
                    units=1,
                    meta={
                        "ok": bool(file_action.get("ok")),
                        "filename": file_action.get("filename"),
                        "error": file_action.get("error"),
                    },
                    commit=True,
                )

        if question_requests_rename(ctx.question):
            _apply_rename(ctx)

        _post_formatted(
            ctx,
            hedge=bool(result.get("hedge")),
            chunks=result.get("retrieved_chunks"),
        )
        _record_mention(ctx, workflow=workflow, hedge=bool(result.get("hedge")))
        logger.info(
            "slack_agent_reply_ok tenant_id=%s channel=%s workflow=%s hedge=%s "
            "chunks=%s attachments=%s rename=%s",
            ctx.tenant_id,
            ctx.channel,
            workflow,
            result.get("hedge"),
            len(result.get("retrieved_chunks") or []),
            len(ctx.attached_payload),
            (ctx.rename_action or {}).get("ok"),
        )
        return {
            "ok": True,
            "denied": False,
            "answer": ctx.answer,
            "hedge": bool(result.get("hedge")),
            "workflow": workflow,
            "attachments": len(ctx.attached_payload),
            "file_action": ctx.file_action,
            "rename_action": ctx.rename_action,
        }


class RenameDeliveryStrategy:
    """Org-copy / Slack title rename then formatted post."""

    def deliver(self, ctx: DeliveryContext) -> dict[str, Any]:
        result = ctx.agent_result or {}
        workflow = str(result.get("workflow") or ctx.pre_workflow or "file_rename")
        ctx.workflow = workflow
        ctx.answer = str(result.get("answer") or "")
        _apply_rename(ctx)
        _post_formatted(
            ctx,
            hedge=bool(result.get("hedge")),
            chunks=result.get("retrieved_chunks"),
        )
        _record_mention(ctx, workflow=workflow, hedge=bool(result.get("hedge")))
        logger.info(
            "slack_agent_reply_ok tenant_id=%s channel=%s workflow=%s hedge=%s "
            "chunks=%s attachments=%s rename=%s",
            ctx.tenant_id,
            ctx.channel,
            workflow,
            result.get("hedge"),
            len(result.get("retrieved_chunks") or []),
            len(ctx.attached_payload),
            (ctx.rename_action or {}).get("ok"),
        )
        return {
            "ok": True,
            "denied": False,
            "answer": ctx.answer,
            "hedge": bool(result.get("hedge")),
            "workflow": workflow,
            "attachments": len(ctx.attached_payload),
            "file_action": ctx.file_action,
            "rename_action": ctx.rename_action,
        }


class LibraryConfirmStrategy:
    """Workflow-library store/list/copy/edit confirmations (no RAG compose)."""

    def deliver(self, ctx: DeliveryContext) -> dict[str, Any]:
        pre_workflow = ctx.pre_workflow
        slack_user = ctx.slack_user
        action: dict[str, Any]

        if pre_workflow == "workflow_store":
            action = store_workflow_from_slack(
                db=ctx.db,
                client_id=str(ctx.tenant_id),
                upload_root=ctx.upload_root,
                attached_evidence=ctx.attached_payload,
                created_by_slack_user_id=slack_user,
                enqueue_ingest=True,
            )
            record_usage(
                ctx.db,
                ctx.tenant_id,
                EVENT_WORKFLOW_STORE,
                units=1,
                meta={
                    "ok": bool(action.get("ok")),
                    "created": action.get("created"),
                    "template_id": (action.get("template") or {}).get("id"),
                    "error": action.get("error"),
                },
                commit=True,
            )
        elif pre_workflow == "workflow_list":
            action = list_workflows_for_slack(
                db=ctx.db,
                client_id=str(ctx.tenant_id),
                question=ctx.question,
                slack_user_id=slack_user,
            )
        elif pre_workflow == "workflow_copy":
            if not slack_user:
                action = {
                    "ok": False,
                    "confirmation": (
                        "I couldn't identify who is copying. Try again from Slack."
                    ),
                }
            else:
                action = copy_workflow_for_slack(
                    db=ctx.db,
                    client_id=str(ctx.tenant_id),
                    upload_root=ctx.upload_root,
                    question=ctx.question,
                    slack_user_id=slack_user,
                )
                record_usage(
                    ctx.db,
                    ctx.tenant_id,
                    EVENT_WORKFLOW_COPY,
                    units=1,
                    meta={
                        "ok": bool(action.get("ok")),
                        "template_id": (action.get("template") or {}).get("id"),
                        "error": action.get("error"),
                    },
                    commit=True,
                )
        else:  # workflow_edit
            if not slack_user:
                action = {
                    "ok": False,
                    "confirmation": (
                        "I couldn't identify who owns the draft. Try again from Slack."
                    ),
                }
            else:
                action = edit_workflow_draft_for_slack(
                    db=ctx.db,
                    client_id=str(ctx.tenant_id),
                    question=ctx.question,
                    slack_user_id=slack_user,
                )

        ctx.workflow_action = action
        answer = str(action.get("confirmation") or "")
        advice_meta: dict[str, Any] | None = None

        # J11: store (+ optional advise) in one ask — append grounded advice
        if (
            pre_workflow == "workflow_store"
            and bool(action.get("ok"))
            and question_requests_workflow_advice(ctx.question)
        ):
            advice_evidence = list(ctx.attached_payload)
            tpl = action.get("template") or {}
            tid_str = str(tpl.get("id") or "").strip()
            if tid_str and not evidence_has_usable_text(advice_evidence):
                enriched = enrich_evidence_for_advice(
                    db=ctx.db,
                    client_id=str(ctx.tenant_id),
                    question=f"Advise on workflow {tid_str}",
                    attached_evidence=[],
                    slack_user_id=slack_user,
                )
                if enriched.get("ok"):
                    advice_evidence = list(enriched.get("evidence") or [])
            if evidence_has_usable_text(advice_evidence):
                advice_question = (
                    "Advise how we can make this workflow work based on "
                    "the attached workflow file."
                )
                advice_result = ctx.invoke(
                    client_id=str(ctx.tenant_id),
                    question=advice_question,
                    conversation_id=ctx.conversation_id,
                    settings=ctx.settings,
                    db_factory=ctx.db_factory,
                    record_usage=True,
                    attached_evidence=advice_evidence,
                )
                advice_text = str(advice_result.get("answer") or "").strip()
                if advice_text:
                    answer = f"{answer}\n\n{MSG_ADVICE_HEADER}\n{advice_text}".strip()
                advice_meta = {
                    "ok": True,
                    "hedge": bool(advice_result.get("hedge")),
                    "workflow": advice_result.get("workflow"),
                }
            else:
                answer = f"{answer}\n\n{MSG_ADVICE_NO_EVIDENCE}".strip()
                advice_meta = {"ok": False, "error": "no_evidence"}

        ctx.answer = answer
        ctx.combined_advice = advice_meta
        ctx.post(
            bot_token=ctx.bot_token,
            channel=ctx.channel,
            text=answer,
            thread_ts=ctx.thread_ts,
        )
        record_usage(
            ctx.db,
            ctx.tenant_id,
            EVENT_SLACK_MENTION,
            units=1,
            meta={
                "event_type": ctx.event.get("type"),
                "channel": ctx.channel,
                "team_id": ctx.team_id,
                "workflow": pre_workflow,
                "attachments": len(ctx.attached_payload),
                "workflow_ok": bool(action.get("ok")),
                "combined_advice": advice_meta,
            },
            commit=True,
        )
        logger.info(
            "slack_workflow_library_ok tenant_id=%s workflow=%s ok=%s advice=%s",
            ctx.tenant_id,
            pre_workflow,
            action.get("ok"),
            bool(advice_meta),
        )
        return {
            "ok": True,
            "denied": False,
            "answer": answer,
            "hedge": False,
            "workflow": pre_workflow,
            "attachments": len(ctx.attached_payload),
            "workflow_action": action,
            "combined_advice": advice_meta,
        }


class AdviseDeliveryStrategy:
    """Post after workflow_advise compose (or early no-evidence confirmation)."""

    def deliver(self, ctx: DeliveryContext) -> dict[str, Any]:
        # Early path: RunAgent already set answer without agent_result
        if ctx.agent_result is None and ctx.answer:
            ctx.post(
                bot_token=ctx.bot_token,
                channel=ctx.channel,
                text=ctx.answer,
                thread_ts=ctx.thread_ts,
            )
            _record_mention(
                ctx,
                workflow="workflow_advise",
                hedge=True,
                extra_meta={"advise_ok": False},
            )
            return {
                "ok": True,
                "denied": False,
                "answer": ctx.answer,
                "hedge": True,
                "workflow": "workflow_advise",
                "attachments": len(ctx.attached_payload),
            }
        return DefaultPostStrategy().deliver(ctx)


_DEFAULT = DefaultPostStrategy()
_PDF = PdfUploadStrategy()
_RENAME = RenameDeliveryStrategy()
_LIBRARY = LibraryConfirmStrategy()
_ADVISE = AdviseDeliveryStrategy()

DELIVERY_STRATEGIES: dict[str, DeliveryStrategy] = {
    "file_pdf_export": _PDF,
    "file_rename": _RENAME,
    "workflow_store": _LIBRARY,
    "workflow_list": _LIBRARY,
    "workflow_copy": _LIBRARY,
    "workflow_edit": _LIBRARY,
    "workflow_advise": _ADVISE,
}


def resolve_delivery_strategy(
    workflow: str | None,
    *,
    pre_workflow: str | None = None,
) -> DeliveryStrategy:
    """Pick DeliveryStrategy by workflow name / ``WorkflowMeta.delivery_hint``."""
    key = (workflow or pre_workflow or "qa").strip()
    if key in DELIVERY_STRATEGIES:
        return DELIVERY_STRATEGIES[key]
    hint = get_workflow_meta(key).delivery_hint
    if hint == "pdf_upload":
        return _PDF
    if hint == "rename":
        return _RENAME
    if hint == "library_confirm":
        return _LIBRARY
    return _DEFAULT


def get_delivery_strategy(workflow: str | None) -> DeliveryStrategy:
    """Public alias used by the reply pipeline."""
    return resolve_delivery_strategy(workflow)


__all__ = [
    "DELIVERY_STRATEGIES",
    "AdviseDeliveryStrategy",
    "DefaultPostStrategy",
    "DeliveryContext",
    "DeliveryStrategy",
    "LibraryConfirmStrategy",
    "PdfUploadStrategy",
    "RenameDeliveryStrategy",
    "get_delivery_strategy",
    "resolve_delivery_strategy",
]

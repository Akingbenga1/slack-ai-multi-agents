"""Mention/DM → LangGraph grounded reply (Sprint 14) + file actions (Sprint 23)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.agent.nodes.route import classify_workflow, question_requests_workflow_advice
from api.app.agent.run import run_agent
from api.app.agent.state import FILE_HEAVY_WORKFLOWS
from api.app.billing.plans import plan_is_active, tenant_has_entitlement, tenant_is_suspended
from api.app.db.session import SessionLocal
from api.app.governance.budgets import BudgetDecision, check_budget
from api.app.governance.usage import (
    EVENT_FILE_JOB,
    EVENT_FILE_RENAME,
    EVENT_PDF_GENERATE,
    EVENT_SLACK_MENTION,
    EVENT_WORKFLOW_COPY,
    EVENT_WORKFLOW_STORE,
    record_usage,
)
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings
from api.app.slack.attachments import (
    evidence_has_usable_text,
    files_from_event,
    intake_attachments,
)
from api.app.slack.echo import (
    conversation_id_for_event,
    post_message,
    question_from_event,
    reply_thread_ts,
)
from api.app.slack.file_actions import (
    MSG_FILE_JOB_DENIED,
    MSG_PDF_NO_ATTACHMENT,
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
from api.app.tenant import set_client_id

logger = get_logger("api.slack.agent_reply")

WORKFLOW_LIBRARY_WORKFLOWS = frozenset(
    {"workflow_store", "workflow_list", "workflow_copy", "workflow_edit"}
)

MSG_PLAN_INACTIVE = (
    "Your organisation's plan is inactive, so I can't answer right now. "
    "An admin can renew billing in the org portal to restore agent replies."
)

MSG_TENANT_SUSPENDED = (
    "Your organisation is suspended on the platform, so I can't answer right now. "
    "Contact the platform owner for support."
)

MSG_AGENT_DISABLED = (
    "Agent replies are not enabled for your organisation's plan. "
    "Ask an admin to check entitlements in the org portal."
)

MSG_BUDGET_EXCEEDED = (
    "Your organisation has reached its {window} {resource} budget "
    "(used {used} of {limit}). Try again later, or ask an admin to review usage."
)

MSG_NO_BUDGET = (
    "Your organisation has no token budget configured, so I can't answer right now. "
    "Ask an admin to check the plan in the org portal."
)


def entitlement_slack_message(decision: BudgetDecision) -> str:
    """Clear Slack copy when plan/budget blocks the agent."""
    if decision.reason == "plan_inactive":
        return MSG_PLAN_INACTIVE
    if decision.reason == "no_budget":
        return MSG_NO_BUDGET
    if decision.reason == "budget_exceeded":
        return MSG_BUDGET_EXCEEDED.format(
            window=decision.window or "current",
            resource=decision.resource,
            used=decision.used,
            limit=decision.limit,
        )
    return MSG_PLAN_INACTIVE


def check_agent_entitlement(
    db: Session,
    tenant_id: UUID | str,
    *,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """
    Allow agent path only for active plan with agent entitlement + token headroom.

    Returns (allowed, denial_message). denial_message is empty when allowed.
    """
    tid = UUID(str(tenant_id))
    if tenant_is_suspended(db, tid):
        return False, MSG_TENANT_SUSPENDED
    if not plan_is_active(db, tid):
        return False, MSG_PLAN_INACTIVE
    if not tenant_has_entitlement(db, tid, "agent"):
        return False, MSG_AGENT_DISABLED

    decision = check_budget(
        db,
        tid,
        "tokens",
        units=1,
        now=now,
        require_active_plan=True,
    )
    if not decision.allowed:
        return False, entitlement_slack_message(decision)
    return True, ""


def check_file_job_entitlement(
    db: Session,
    tenant_id: UUID | str,
    *,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """
    Extra gate for heavy file/PDF jobs (jobs_daily budget + agent plan).

    Returns (allowed, denial_message).
    """
    tid = UUID(str(tenant_id))
    allowed, denial = check_agent_entitlement(db, tid, now=now)
    if not allowed:
        return False, denial

    decision = check_budget(
        db,
        tid,
        "jobs",
        units=1,
        now=now,
        require_active_plan=True,
    )
    if not decision.allowed:
        reason = entitlement_slack_message(decision)
        return False, MSG_FILE_JOB_DENIED.format(reason=reason)
    return True, ""


def process_agent_reply(
    *,
    tenant_id: UUID | str,
    bot_token: str,
    event: dict[str, Any],
    team_id: str | None = None,
    settings: Settings | None = None,
    db_factory: Optional[Callable[[], Session]] = None,
    run_agent_fn: Optional[Callable[..., dict[str, Any]]] = None,
    post_fn: Optional[Callable[..., dict[str, Any]]] = None,
) -> dict[str, Any]:
    """
    Budget-gate → attachment intake → run_agent → optional PDF upload → post.

    Designed to run in a FastAPI BackgroundTask with a fresh DB session.
    """
    settings = settings or get_settings()
    factory = db_factory or SessionLocal
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

    db = factory()
    try:
        allowed, denial = check_agent_entitlement(db, tid)
        if not allowed:
            logger.info(
                "slack_agent_denied tenant_id=%s reason=%s",
                tid,
                denial[:80],
            )
            post(
                bot_token=bot_token,
                channel=channel,
                text=denial,
                thread_ts=thread_ts,
            )
            return {"ok": True, "denied": True, "reason": denial}

        if pre_workflow in FILE_HEAVY_WORKFLOWS:
            ok_job, job_denial = check_file_job_entitlement(db, tid)
            if not ok_job:
                logger.info(
                    "slack_file_job_denied tenant_id=%s workflow=%s",
                    tid,
                    pre_workflow,
                )
                post(
                    bot_token=bot_token,
                    channel=channel,
                    text=job_denial,
                    thread_ts=thread_ts,
                )
                return {
                    "ok": True,
                    "denied": True,
                    "reason": job_denial,
                    "workflow": pre_workflow,
                }

        attached_payload: list[dict[str, Any]] = []
        intake_errors: list[str] = []
        if has_file_refs:
            upload_root = Path(settings.upload_dir)
            intake = intake_attachments(
                client_id=str(tid),
                bot_token=bot_token,
                event=event,
                upload_root=upload_root,
            )
            attached_payload = [e.to_dict() for e in intake.evidence]
            intake_errors = list(intake.errors)
            record_usage(
                db,
                tid,
                EVENT_FILE_JOB,
                units=1,
                meta={
                    "refs": len(intake.refs),
                    "parsed": len(
                        [e for e in intake.evidence if (e.text or "").strip()]
                    ),
                    "errors": intake_errors[:5],
                },
                commit=True,
            )

        upload_root = Path(settings.upload_dir)
        slack_user = str(event.get("user") or "").strip() or None

        # Shared workflow library (Sprint 24) — confirmations without full RAG compose
        if pre_workflow in WORKFLOW_LIBRARY_WORKFLOWS:
            action: dict[str, Any]
            if pre_workflow == "workflow_store":
                action = store_workflow_from_slack(
                    db=db,
                    client_id=str(tid),
                    upload_root=upload_root,
                    attached_evidence=attached_payload,
                    created_by_slack_user_id=slack_user,
                    enqueue_ingest=True,
                )
                record_usage(
                    db,
                    tid,
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
                    db=db,
                    client_id=str(tid),
                    question=question,
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
                        db=db,
                        client_id=str(tid),
                        upload_root=upload_root,
                        question=question,
                        slack_user_id=slack_user,
                    )
                    record_usage(
                        db,
                        tid,
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
                        db=db,
                        client_id=str(tid),
                        question=question,
                        slack_user_id=slack_user,
                    )

            answer = str(action.get("confirmation") or "")
            advice_meta: dict[str, Any] | None = None

            # J11: store (+ optional advise) in one ask — append grounded advice
            if (
                pre_workflow == "workflow_store"
                and bool(action.get("ok"))
                and question_requests_workflow_advice(question)
            ):
                advice_evidence = list(attached_payload)
                tpl = action.get("template") or {}
                tid_str = str(tpl.get("id") or "").strip()
                if tid_str and not evidence_has_usable_text(advice_evidence):
                    enriched = enrich_evidence_for_advice(
                        db=db,
                        client_id=str(tid),
                        question=f"Advise on workflow {tid_str}",
                        attached_evidence=[],
                        slack_user_id=slack_user,
                    )
                    if enriched.get("ok"):
                        advice_evidence = list(enriched.get("evidence") or [])
                if evidence_has_usable_text(advice_evidence):
                    # Force advise classification (store phrasing would win otherwise)
                    advice_question = (
                        "Advise how we can make this workflow work based on "
                        "the attached workflow file."
                    )
                    advice_result = invoke(
                        client_id=str(tid),
                        question=advice_question,
                        conversation_id=conversation_id,
                        settings=settings,
                        db_factory=factory,
                        record_usage=True,
                        attached_evidence=advice_evidence,
                    )
                    advice_text = str(advice_result.get("answer") or "").strip()
                    if advice_text:
                        answer = (
                            f"{answer}\n\n{MSG_ADVICE_HEADER}\n{advice_text}"
                        ).strip()
                    advice_meta = {
                        "ok": True,
                        "hedge": bool(advice_result.get("hedge")),
                        "workflow": advice_result.get("workflow"),
                    }
                else:
                    answer = f"{answer}\n\n{MSG_ADVICE_NO_EVIDENCE}".strip()
                    advice_meta = {"ok": False, "error": "no_evidence"}

            post(
                bot_token=bot_token,
                channel=channel,
                text=answer,
                thread_ts=thread_ts,
            )
            record_usage(
                db,
                tid,
                EVENT_SLACK_MENTION,
                units=1,
                meta={
                    "event_type": event.get("type"),
                    "channel": channel,
                    "team_id": team_id,
                    "workflow": pre_workflow,
                    "attachments": len(attached_payload),
                    "workflow_ok": bool(action.get("ok")),
                    "combined_advice": advice_meta,
                },
                commit=True,
            )
            logger.info(
                "slack_workflow_library_ok tenant_id=%s workflow=%s ok=%s advice=%s",
                tid,
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
                "attachments": len(attached_payload),
                "workflow_action": action,
                "combined_advice": advice_meta,
            }

        # File-grounded workflow advice (Sprint 24.4) — enrich evidence then compose
        if pre_workflow == "workflow_advise":
            enriched = enrich_evidence_for_advice(
                db=db,
                client_id=str(tid),
                question=question,
                attached_evidence=attached_payload,
                slack_user_id=slack_user,
            )
            if not enriched.get("ok"):
                answer = str(
                    enriched.get("confirmation") or MSG_ADVICE_NO_EVIDENCE
                )
                post(
                    bot_token=bot_token,
                    channel=channel,
                    text=answer,
                    thread_ts=thread_ts,
                )
                record_usage(
                    db,
                    tid,
                    EVENT_SLACK_MENTION,
                    units=1,
                    meta={
                        "event_type": event.get("type"),
                        "channel": channel,
                        "team_id": team_id,
                        "workflow": pre_workflow,
                        "attachments": len(attached_payload),
                        "advise_ok": False,
                    },
                    commit=True,
                )
                return {
                    "ok": True,
                    "denied": False,
                    "answer": answer,
                    "hedge": True,
                    "workflow": pre_workflow,
                    "attachments": len(attached_payload),
                }
            attached_payload = list(enriched.get("evidence") or attached_payload)

        result = invoke(
            client_id=str(tid),
            question=question,
            conversation_id=conversation_id,
            settings=settings,
            db_factory=factory,
            record_usage=True,
            attached_evidence=attached_payload,
        )
        workflow = str(result.get("workflow") or pre_workflow)
        answer = str(result.get("answer") or "")
        file_action: dict[str, Any] | None = None
        rename_action: dict[str, Any] | None = None

        if workflow == "file_pdf_export" and not bool(result.get("hedge")):
            if not evidence_has_usable_text(attached_payload):
                answer = (
                    f"{answer}\n\n{MSG_PDF_NO_ATTACHMENT}".strip()
                    if answer
                    else MSG_PDF_NO_ATTACHMENT
                )
            else:
                used_rag = any(
                    (c.get("kind") or "") != "attachment"
                    for c in (result.get("retrieved_chunks") or [])
                    if isinstance(c, dict)
                )
                file_action = produce_and_upload_analysis_pdf(
                    client_id=str(tid),
                    bot_token=bot_token,
                    channel=str(channel),
                    analysis_text=answer,
                    attached_evidence=attached_payload,
                    upload_root=upload_root,
                    thread_ts=thread_ts,
                    title="Competitor analysis",
                    used_rag=used_rag,
                )
                confirmation = str(file_action.get("confirmation") or "")
                if confirmation:
                    answer = f"{answer}\n\n{confirmation}".strip()
                record_usage(
                    db,
                    tid,
                    EVENT_PDF_GENERATE,
                    units=1,
                    meta={
                        "ok": bool(file_action.get("ok")),
                        "filename": file_action.get("filename"),
                        "error": file_action.get("error"),
                    },
                    commit=True,
                )

        # Rename: standalone workflow, or J10 combined PDF + rename ask.
        if workflow == "file_rename" or (
            workflow == "file_pdf_export" and question_requests_rename(question)
        ):
            rename_action = rename_slack_file_or_copy(
                client_id=str(tid),
                upload_root=upload_root,
                question=question,
                attached_evidence=attached_payload,
                bot_token=bot_token,
            )
            # Keep evidence paths in sync if org copy moved (follow-on actions)
            new_rel = rename_action.get("stored_relative_path")
            new_name = rename_action.get("new_filename")
            if new_rel and attached_payload:
                for item in attached_payload:
                    if isinstance(item, dict) and item.get("client_id") == str(tid):
                        item["stored_relative_path"] = new_rel
                        if new_name:
                            item["filename"] = new_name
                        break
            rename_note = str(rename_action.get("confirmation") or "")
            if rename_note:
                answer = f"{answer}\n\n{rename_note}".strip() if answer else rename_note
            record_usage(
                db,
                tid,
                EVENT_FILE_RENAME,
                units=1,
                meta={
                    "ok": bool(rename_action.get("ok")),
                    "mode": rename_action.get("mode"),
                    "new_filename": rename_action.get("new_filename"),
                    "error": rename_action.get("error")
                    or rename_action.get("slack_error"),
                },
                commit=True,
            )

        text = format_slack_reply(
            answer,
            chunks=result.get("retrieved_chunks"),
            hedge=bool(result.get("hedge")),
        )
        post(
            bot_token=bot_token,
            channel=channel,
            text=text,
            thread_ts=thread_ts,
        )
        record_usage(
            db,
            tid,
            EVENT_SLACK_MENTION,
            units=1,
            meta={
                "event_type": event.get("type"),
                "channel": channel,
                "team_id": team_id,
                "workflow": workflow,
                "hedge": bool(result.get("hedge")),
                "usage_tokens": int(result.get("usage_tokens") or 0),
                "attachments": len(attached_payload),
                "intake_errors": intake_errors[:3],
                "pdf_ok": (file_action or {}).get("ok"),
                "rename_ok": (rename_action or {}).get("ok"),
            },
            commit=True,
        )
        logger.info(
            "slack_agent_reply_ok tenant_id=%s channel=%s workflow=%s hedge=%s "
            "chunks=%s attachments=%s rename=%s",
            tid,
            channel,
            workflow,
            result.get("hedge"),
            len(result.get("retrieved_chunks") or []),
            len(attached_payload),
            (rename_action or {}).get("ok"),
        )
        return {
            "ok": True,
            "denied": False,
            "answer": answer,
            "hedge": bool(result.get("hedge")),
            "workflow": workflow,
            "attachments": len(attached_payload),
            "file_action": file_action,
            "rename_action": rename_action,
        }
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

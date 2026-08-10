"""Slack shared workflow library actions (Sprint 24)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from api.app.logging_config import get_logger
from api.app.slack.attachments import AttachedEvidence, evidence_has_usable_text
from api.app.workflows.library import (
    MSG_NOT_FOUND,
    copy_template,
    list_templates,
    resolve_template_for_advice,
    store_from_attached_evidence,
    template_to_dict,
    template_to_evidence,
    update_personal_draft,
)

logger = get_logger("api.slack.workflow_actions")

MSG_STORE_NO_ATTACHMENT = (
    "I couldn't find a workflow file to store. Attach a supported file "
    "(PDF, DOCX, XLSX, CSV, MD, or TXT) and ask me to store it in the "
    "shared library."
)

MSG_STORE_OK = (
    "Stored *{title}* in your org's shared workflow library "
    "(id `{template_id}`).\n"
    "• *Where:* org shared library (also visible in `/app/workflows`)\n"
    "• *Colleagues:* ask me to *list workflows*, then *copy workflow* "
    "`{template_id}` for a personal draft — copies never change this original.\n"
    "• *Advice:* ask me to *advise how to make this workflow work* "
    "(or include that in the same message next time)."
)

MSG_STORE_IDEMPOTENT = (
    "*{title}* was already in the shared library (id `{template_id}`). "
    "No duplicate created.\n"
    "• *Where:* org shared library (also visible in `/app/workflows`)\n"
    "• Colleagues can *list* / *copy* it; personal drafts leave this original unchanged.\n"
    "• Ask me to *advise* on this workflow (by attachment or id) for grounded guidance."
)

MSG_STORE_FAILED = (
    "I couldn't store that workflow file: {reason}. "
    "Try again with a supported attachment, or ask an admin to check uploads."
)

MSG_LIST_EMPTY = (
    "No shared workflow templates found for your organisation yet. "
    "Upload a workflow description and ask me to store it."
)

MSG_LIST_HEADER = "Shared workflow library ({count}):"

MSG_COPY_OK = (
    "Created your personal draft *{title}* (id `{template_id}`) from "
    "*{parent_title}*. Edit your copy anytime — the shared original stays unchanged."
)

MSG_COPY_FAILED = (
    "I couldn't copy that workflow: {reason}."
)

MSG_EDIT_OK = (
    "Updated your personal draft *{title}* (id `{template_id}`, v{version})."
)

MSG_EDIT_FAILED = (
    "I couldn't update that draft: {reason}."
)

MSG_ADVICE_NO_EVIDENCE = (
    "I need the workflow file (or a stored template id) to give grounded "
    "advice. Attach the description, or ask me to advise on a library "
    "template by id after listing workflows."
)

MSG_ADVICE_HEADER = "*Advice* (grounded in the workflow file):"


def _first_usable(
    evidence: list[AttachedEvidence] | list[dict[str, Any]],
    *,
    client_id: str,
) -> AttachedEvidence | dict[str, Any] | None:
    cid = str(client_id)
    for item in evidence:
        if isinstance(item, AttachedEvidence):
            if item.client_id == cid and (
                (item.text or "").strip() or item.stored_relative_path
            ):
                return item
        elif isinstance(item, dict) and item.get("client_id") == cid:
            if (item.get("text") or "").strip() or item.get("stored_relative_path"):
                return item
    return None


def _as_dict(item: AttachedEvidence | dict[str, Any]) -> dict[str, Any]:
    if isinstance(item, AttachedEvidence):
        return item.to_dict()
    return dict(item)


_COPY_ID = re.compile(
    r"\b(?:copy|duplicate)\b.*?\b(?:workflow|template)\b.*?\b([0-9a-f]{8}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
    re.I | re.S,
)
_COPY_ID_ALT = re.compile(
    r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
    re.I,
)
_EDIT_TITLE = re.compile(
    r"\b(?:rename|retitle|title)\s+(?:my\s+)?(?:draft|copy|template)\s+to\s+[\"']?(.+?)[\"']?\s*$",
    re.I,
)
_LIST_QUERY = re.compile(
    r"\b(?:list|show|find|search)\s+(?:shared\s+)?workflows?\b(?:\s+(?:for|matching|named)\s+(.+))?$",
    re.I,
)


def extract_copy_template_id(question: str) -> str | None:
    text = (question or "").strip()
    m = _COPY_ID.search(text)
    if m:
        return m.group(1)
    # Fallback: bare UUID when copy intent already classified
    if re.search(r"\b(copy|duplicate)\b", text, re.I):
        m2 = _COPY_ID_ALT.search(text)
        if m2:
            return m2.group(1)
    return None


def extract_list_query(question: str) -> str | None:
    m = _LIST_QUERY.search((question or "").strip())
    if not m:
        return None
    q = (m.group(1) or "").strip()
    return q or None


def store_workflow_from_slack(
    *,
    db: Session,
    client_id: str,
    upload_root: Path,
    attached_evidence: list[AttachedEvidence] | list[dict[str, Any]],
    created_by_slack_user_id: str | None = None,
    title: str | None = None,
    enqueue_ingest: bool = True,
) -> dict[str, Any]:
    """Persist attachment into shared library; idempotent by hash / file_id."""
    usable = _first_usable(attached_evidence, client_id=client_id)
    if usable is None:
        return {
            "ok": False,
            "error": "no_attachment",
            "confirmation": MSG_STORE_NO_ATTACHMENT,
        }

    try:
        result = store_from_attached_evidence(
            db,
            client_id=client_id,
            upload_root=upload_root,
            evidence=_as_dict(usable),
            title=title,
            created_by_slack_user_id=created_by_slack_user_id,
            enqueue_ingest=enqueue_ingest,
        )
        db.commit()
        tpl = result.template
        confirmation = (
            MSG_STORE_OK if result.created else MSG_STORE_IDEMPOTENT
        ).format(title=tpl.title, template_id=tpl.id)
        return {
            "ok": True,
            "created": result.created,
            "template": template_to_dict(tpl),
            "confirmation": confirmation,
            "ingested_queued": result.ingested_queued,
        }
    except Exception as exc:
        db.rollback()
        logger.warning(
            "workflow_store_failed client_id=%s err=%s",
            client_id,
            exc,
        )
        return {
            "ok": False,
            "error": str(exc)[:300],
            "confirmation": MSG_STORE_FAILED.format(reason=str(exc)[:120]),
        }


def format_template_list(
    rows: list[Any],
) -> str:
    if not rows:
        return MSG_LIST_EMPTY
    lines = [MSG_LIST_HEADER.format(count=len(rows))]
    for row in rows:
        vis = getattr(row, "visibility", "shared")
        mark = " (your draft)" if vis == "personal" else ""
        lines.append(
            f"• *{row.title}*{mark} — `{row.id}` — `{row.original_filename}`"
        )
    lines.append(
        "Ask me to *copy* a template by id to create your own editable draft."
    )
    return "\n".join(lines)


def list_workflows_for_slack(
    *,
    db: Session,
    client_id: str,
    question: str,
    slack_user_id: str | None = None,
) -> dict[str, Any]:
    q = extract_list_query(question)
    rows = list_templates(
        db,
        client_id=client_id,
        q=q,
        include_personal_for=slack_user_id,
        limit=25,
    )
    return {
        "ok": True,
        "count": len(rows),
        "templates": [template_to_dict(r) for r in rows],
        "confirmation": format_template_list(rows),
    }


def copy_workflow_for_slack(
    *,
    db: Session,
    client_id: str,
    upload_root: Path,
    question: str,
    slack_user_id: str,
    template_id: str | None = None,
) -> dict[str, Any]:
    tid = template_id or extract_copy_template_id(question)
    if not tid:
        return {
            "ok": False,
            "error": "missing_template_id",
            "confirmation": MSG_COPY_FAILED.format(
                reason="include the template id from the library list"
            ),
        }
    try:
        parent = None
        from api.app.workflows.library import get_template

        parent = get_template(db, client_id=client_id, template_id=tid)
        draft = copy_template(
            db,
            client_id=client_id,
            upload_root=upload_root,
            template_id=tid,
            owner_slack_user_id=slack_user_id,
        )
        db.commit()
        return {
            "ok": True,
            "template": template_to_dict(draft),
            "confirmation": MSG_COPY_OK.format(
                title=draft.title,
                template_id=draft.id,
                parent_title=parent.title if parent else tid,
            ),
        }
    except LookupError:
        db.rollback()
        return {
            "ok": False,
            "error": "not_found",
            "confirmation": MSG_COPY_FAILED.format(reason=MSG_NOT_FOUND),
        }
    except Exception as exc:
        db.rollback()
        logger.warning(
            "workflow_copy_failed client_id=%s err=%s",
            client_id,
            exc,
        )
        return {
            "ok": False,
            "error": str(exc)[:300],
            "confirmation": MSG_COPY_FAILED.format(reason=str(exc)[:120]),
        }


def edit_workflow_draft_for_slack(
    *,
    db: Session,
    client_id: str,
    question: str,
    slack_user_id: str,
    template_id: str | None = None,
) -> dict[str, Any]:
    tid = template_id or extract_copy_template_id(question)
    if not tid:
        # Also accept bare UUID for edit intents
        m = _COPY_ID_ALT.search(question or "")
        tid = m.group(1) if m else None
    if not tid:
        return {
            "ok": False,
            "error": "missing_template_id",
            "confirmation": MSG_EDIT_FAILED.format(
                reason="include your draft template id"
            ),
        }

    new_title = None
    m_title = _EDIT_TITLE.search((question or "").strip())
    if m_title:
        new_title = m_title.group(1).strip()

    # Body edit: "update my draft <id>: <text>" / "set body of draft ..."
    new_body = None
    m_body = re.search(
        r"\b(?:set|update|change)\s+(?:the\s+)?(?:body|text|content)\s+"
        r"(?:of\s+)?(?:my\s+)?(?:draft|copy|template)\b[:\s]+(.+)$",
        question or "",
        re.I | re.S,
    )
    if m_body:
        new_body = m_body.group(1).strip()

    if new_title is None and new_body is None:
        return {
            "ok": False,
            "error": "nothing_to_edit",
            "confirmation": MSG_EDIT_FAILED.format(
                reason="say what to change (title or body)"
            ),
        }

    try:
        row = update_personal_draft(
            db,
            client_id=client_id,
            template_id=tid,
            owner_slack_user_id=slack_user_id,
            title=new_title,
            body_text=new_body,
        )
        db.commit()
        return {
            "ok": True,
            "template": template_to_dict(row),
            "confirmation": MSG_EDIT_OK.format(
                title=row.title,
                template_id=row.id,
                version=row.version,
            ),
        }
    except PermissionError as exc:
        db.rollback()
        return {
            "ok": False,
            "error": "forbidden",
            "confirmation": MSG_EDIT_FAILED.format(reason=str(exc)),
        }
    except LookupError:
        db.rollback()
        return {
            "ok": False,
            "error": "not_found",
            "confirmation": MSG_EDIT_FAILED.format(reason=MSG_NOT_FOUND),
        }
    except Exception as exc:
        db.rollback()
        return {
            "ok": False,
            "error": str(exc)[:300],
            "confirmation": MSG_EDIT_FAILED.format(reason=str(exc)[:120]),
        }


def enrich_evidence_for_advice(
    *,
    db: Session,
    client_id: str,
    question: str,
    attached_evidence: list[AttachedEvidence] | list[dict[str, Any]],
    slack_user_id: str | None = None,
) -> dict[str, Any]:
    """
    Build evidence for ``workflow_advise``.

    Prefers usable attachments; otherwise loads a tenant-scoped stored
    template referenced by id in the question.
    """
    evidence: list[dict[str, Any]] = []
    for item in attached_evidence or []:
        evidence.append(_as_dict(item))

    if evidence_has_usable_text(evidence):
        return {
            "ok": True,
            "evidence": evidence,
            "source": "attachment",
            "template": None,
        }

    row = resolve_template_for_advice(
        db,
        client_id=client_id,
        question=question,
        slack_user_id=slack_user_id,
    )
    if row is not None and (row.body_text or "").strip():
        ev = template_to_evidence(row)
        return {
            "ok": True,
            "evidence": [ev],
            "source": "library",
            "template": template_to_dict(row),
        }

    return {
        "ok": False,
        "error": "no_evidence",
        "evidence": evidence,
        "source": None,
        "template": None,
        "confirmation": MSG_ADVICE_NO_EVIDENCE,
    }

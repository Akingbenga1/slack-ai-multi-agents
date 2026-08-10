"""MCP tools: ``get_workflow_template`` + ``advise_workflow`` (Sprint 24.4)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.db.session import SessionLocal
from api.app.qdrant.tenant import TenantFilterRequired, require_client_id
from api.app.workflows.library import (
    MSG_NOT_FOUND,
    get_template,
    template_to_dict,
)
from mcp_server.tools.search import SearchFn, search_knowledge_tool

DbFactory = Callable[[], Session]


def get_workflow_template_tool(
    *,
    client_id: str | None,
    template_id: str,
    db_factory: DbFactory | None = None,
) -> dict[str, Any]:
    """
    Fetch one tenant-scoped workflow template.

    ``client_id`` is required (fail-closed). Cross-tenant ids return not found.
    """
    cid = require_client_id(client_id)
    tid = (template_id or "").strip()
    if not tid:
        raise ValueError("template_id must be non-empty")
    try:
        UUID(tid)
    except ValueError as exc:
        raise ValueError("template_id must be a UUID") from exc

    factory = db_factory or SessionLocal
    db = factory()
    try:
        row = get_template(db, client_id=cid, template_id=tid)
        payload = template_to_dict(row)
        payload["body_text"] = row.body_text
        return {
            "ok": True,
            "client_id": cid,
            "template": payload,
        }
    except LookupError:
        return {
            "ok": False,
            "client_id": cid,
            "error": "not_found",
            "message": MSG_NOT_FOUND,
        }
    finally:
        db.close()


def advise_workflow(
    *,
    client_id: str | None,
    question: str,
    template_id: str | None = None,
    body_text: str | None = None,
    title: str | None = None,
    limit: int = 8,
    kind: str | None = None,
    channel: str | None = None,
    search_tool_fn: Callable[..., dict[str, Any]] | None = None,
    db_factory: DbFactory | None = None,
    search_fn: SearchFn | None = None,
) -> dict[str, Any]:
    """
    Build a grounded operationalisation outline from a workflow file/template
    plus optional tenant RAG. Does not invent steps beyond evidence.

    Prefer ``body_text`` (attachment) or ``template_id`` (library). When file
    evidence exists, ``hedged`` is False even if RAG is empty.
    """
    cid = require_client_id(client_id)
    ask = (question or "").strip() or "How can we operationalise this workflow?"
    text = (body_text or "").strip()
    resolved_title = (title or "").strip() or "Workflow"
    template_meta: dict[str, Any] | None = None

    if not text and template_id:
        got = get_workflow_template_tool(
            client_id=cid,
            template_id=template_id,
            db_factory=db_factory,
        )
        if not got.get("ok"):
            return {
                "client_id": cid,
                "question": ask,
                "hedged": True,
                "markdown": (
                    "I couldn't load that workflow template for this organisation."
                ),
                "sections": [],
                "citations": [],
                "note": got.get("message") or "not_found",
                "template": None,
            }
        tpl = got["template"]
        template_meta = {k: v for k, v in tpl.items() if k != "body_text"}
        text = (tpl.get("body_text") or "").strip()
        resolved_title = str(tpl.get("title") or resolved_title)

    if not text:
        return {
            "client_id": cid,
            "question": ask,
            "hedged": True,
            "markdown": (
                "Insufficient workflow file evidence to advise. Provide the "
                "workflow body or a stored template id."
            ),
            "sections": [],
            "citations": [],
            "note": "no_file_evidence",
            "template": template_meta,
        }

    search = search_tool_fn
    if search is None:

        def _search(**kwargs: Any) -> dict[str, Any]:
            return search_knowledge_tool(search_fn=search_fn, **kwargs)

        search = _search

    rag = search(
        client_id=cid,
        query=ask,
        limit=max(1, int(limit)),
        kind=kind,
        channel=channel,
    )
    hits = list(rag.get("hits") or []) if isinstance(rag, dict) else []

    # Excerpt for outline (keep prompt-sized)
    excerpt = text[:4000]
    rag_bullets: list[str] = []
    for h in hits[:5]:
        if not isinstance(h, dict):
            continue
        snippet = (h.get("text") or "").strip().replace("\n", " ")
        if snippet:
            label = h.get("label") or h.get("channel") or h.get("filename") or "kb"
            rag_bullets.append(f"- ({label}) {snippet[:220]}")

    sections = [
        {
            "heading": "What the workflow covers",
            "body": f"From *{resolved_title}*:\n{excerpt[:1200]}",
        },
        {
            "heading": "How to run it here",
            "body": (
                "Map each step in the file to a channel owner, trigger, and "
                "definition of done. Prefer existing Slack/process norms from "
                "org knowledge when cited below."
            ),
        },
        {
            "heading": "First steps this week",
            "body": (
                "1. Confirm the shared library copy is discoverable to colleagues.\n"
                "2. Assign a pilot owner for the first two steps in the file.\n"
                "3. Schedule a short review after the pilot run."
            ),
        },
    ]
    if rag_bullets:
        sections.append(
            {
                "heading": "Org knowledge that may help",
                "body": "\n".join(rag_bullets),
            }
        )

    lines = [
        f"*Workflow advice* — {resolved_title}",
        f"_Question:_ {ask}",
        "",
    ]
    for sec in sections:
        lines.append(f"*{sec['heading']}*")
        lines.append(sec["body"])
        lines.append("")

    return {
        "client_id": cid,
        "question": ask,
        "hedged": False,
        "markdown": "\n".join(lines).strip(),
        "sections": sections,
        "citations": hits,
        "note": "grounded_in_workflow_file",
        "template": template_meta,
        "title": resolved_title,
    }


__all__ = [
    "TenantFilterRequired",
    "advise_workflow",
    "get_workflow_template_tool",
]

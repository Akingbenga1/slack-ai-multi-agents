"""MCP tool: ``draft_meeting_agenda`` — agenda from tenant knowledge."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from api.app.qdrant.tenant import require_client_id
from api.app.retrieval.types import KnowledgeCitation, KnowledgeSearchResult
from mcp_server.serialize import citation_to_dict, search_result_to_dict
from mcp_server.tools.search import search_knowledge_tool

SearchToolFn = Callable[..., dict[str, Any]]


def draft_meeting_agenda(
    *,
    client_id: str | None,
    topic: str,
    limit: int = 8,
    kind: str | None = None,
    channel: str | None = None,
    search_tool_fn: SearchToolFn | None = None,
) -> dict[str, Any]:
    """
    Build a meeting-agenda draft from retrieved knowledge for one tenant.

    Deterministic (no LLM): numbered items + decision points from evidence.
    Agent compose (Sprint 16.3) may polish on Sonnet.
    """
    cid = require_client_id(client_id)
    subject = (topic or "").strip()
    if not subject:
        raise ValueError("topic must be non-empty")

    search = search_tool_fn or search_knowledge_tool
    raw = search(
        client_id=cid,
        query=subject,
        limit=limit,
        kind=kind,
        channel=channel,
    )
    hits = raw.get("hits") or []
    citations = [_hit_as_citation(h) for h in hits if isinstance(h, dict)]

    items = _agenda_items(subject, citations)
    markdown = _markdown_agenda(subject, items, citations)

    return {
        "client_id": cid,
        "topic": subject,
        "title": f"Meeting agenda: {subject}",
        "items": items,
        "markdown": markdown,
        "citations": [citation_to_dict(c) for c in citations],
        "retrieval": raw
        if "query" in raw
        else search_result_to_dict(
            KnowledgeSearchResult(
                client_id=cid, query=subject, hits=citations, limit=limit
            )
        ),
        "hedged": len(citations) == 0,
        "note": (
            "Insufficient tenant evidence — agenda is a placeholder skeleton."
            if not citations
            else "Draft from retrieved evidence only; review before sharing."
        ),
    }


def _hit_as_citation(h: dict[str, Any]) -> KnowledgeCitation:
    return KnowledgeCitation(
        point_id=str(h.get("point_id") or ""),
        score=float(h.get("score") or 0.0),
        text=str(h.get("text") or ""),
        kind=str(h.get("kind") or "unknown"),
        client_id=str(h.get("client_id") or ""),
        channel=h.get("channel"),
        ts=h.get("ts"),
        user=h.get("user"),
        thread_ts=h.get("thread_ts"),
        filename=h.get("filename"),
        locator=h.get("locator"),
        title=h.get("title"),
        source_format=h.get("source_format"),
        chunk_index=h.get("chunk_index"),
    )


def _agenda_items(
    topic: str, citations: list[KnowledgeCitation]
) -> list[dict[str, Any]]:
    if not citations:
        return [
            {
                "title": "Open / goals",
                "detail": f"Confirm purpose for “{topic}” (no knowledge found yet).",
                "owner": None,
            },
            {
                "title": "Decisions needed",
                "detail": "List decisions once evidence is synced.",
                "owner": None,
            },
            {
                "title": "Next steps",
                "detail": "Assign owners after discussion.",
                "owner": None,
            },
        ]

    items: list[dict[str, Any]] = [
        {
            "title": "Open / goals",
            "detail": f"Align on: {topic}",
            "owner": None,
        }
    ]
    for i, c in enumerate(citations, start=1):
        excerpt = _excerpt(c.text)
        owner = c.user
        items.append(
            {
                "title": f"Topic {i}",
                "detail": f"{excerpt} _(source: {c.short_label()})_",
                "owner": owner,
            }
        )
    items.append(
        {
            "title": "Decisions & owners",
            "detail": "Confirm decisions and owners from the topics above.",
            "owner": None,
        }
    )
    items.append(
        {
            "title": "Wrap / next steps",
            "detail": "Capture action items and follow-ups.",
            "owner": None,
        }
    )
    return items


def _markdown_agenda(
    topic: str,
    items: list[dict[str, Any]],
    citations: list[KnowledgeCitation],
) -> str:
    lines = [f"# Meeting agenda: {topic}", ""]
    for i, item in enumerate(items, start=1):
        owner = item.get("owner")
        owner_bit = f" _(owner: {owner})_" if owner else ""
        lines.append(f"{i}. **{item['title']}**{owner_bit}")
        detail = (item.get("detail") or "").strip()
        if detail:
            lines.append(f"   - {detail}")
        lines.append("")
    if citations:
        lines.append("## Sources")
        for c in citations:
            lines.append(f"- {c.short_label()} (score={c.score:.3f})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _excerpt(text: str, max_len: int = 160) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


__all__ = ["draft_meeting_agenda"]

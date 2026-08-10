"""MCP tool: ``draft_meeting_agenda`` — agenda from tenant knowledge."""

from __future__ import annotations

from typing import Any

from api.app.retrieval.types import KnowledgeCitation
from mcp_server.tools.grounded import (
    SearchToolFn,
    excerpt,
    run_grounded_draft,
)


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
    subject = (topic or "").strip()
    if not subject:
        raise ValueError("topic must be non-empty")

    def outline_fn(citations: list[KnowledgeCitation]) -> dict[str, Any]:
        items = _agenda_items(subject, citations)
        return {
            "topic": subject,
            "title": f"Meeting agenda: {subject}",
            "items": items,
            "markdown": _markdown_agenda(subject, items, citations),
        }

    return run_grounded_draft(
        client_id=client_id,
        query=subject,
        outline_fn=outline_fn,
        limit=limit,
        kind=kind,
        channel=channel,
        search_tool_fn=search_tool_fn,
        empty_note=(
            "Insufficient tenant evidence — agenda is a placeholder skeleton."
        ),
        evidence_note=(
            "Draft from retrieved evidence only; review before sharing."
        ),
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
        items.append(
            {
                "title": f"Topic {i}",
                "detail": f"{excerpt(c.text)} _(source: {c.short_label()})_",
                "owner": c.user,
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


__all__ = ["draft_meeting_agenda"]

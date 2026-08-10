"""MCP tool: ``draft_meeting_brief`` — outline from tenant knowledge."""

from __future__ import annotations

from typing import Any

from api.app.retrieval.types import KnowledgeCitation
from mcp_server.tools.grounded import (
    SearchToolFn,
    excerpt,
    run_grounded_draft,
)


def draft_meeting_brief(
    *,
    client_id: str | None,
    topic: str,
    limit: int = 8,
    kind: str | None = None,
    channel: str | None = None,
    search_tool_fn: SearchToolFn | None = None,
) -> dict[str, Any]:
    """
    Build a meeting-brief draft from retrieved knowledge for one tenant.

    Deterministic (no LLM): sections + bullet evidence excerpts. Sprint 16
    will escalate compose; this tool stays a grounded draft helper for MCP.
    """
    subject = (topic or "").strip()
    if not subject:
        raise ValueError("topic must be non-empty")

    def outline_fn(citations: list[KnowledgeCitation]) -> dict[str, Any]:
        sections = _sections_from_citations(subject, citations)
        return {
            "topic": subject,
            "title": f"Meeting brief: {subject}",
            "sections": sections,
            "markdown": _markdown_brief(subject, sections, citations),
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
            "Insufficient tenant evidence — brief is a placeholder skeleton."
        ),
        evidence_note=(
            "Draft from retrieved evidence only; review before sharing."
        ),
    )


def _sections_from_citations(
    topic: str, citations: list[KnowledgeCitation]
) -> list[dict[str, Any]]:
    if not citations:
        return [
            {
                "heading": "Context",
                "bullets": [
                    f"No tenant knowledge found for “{topic}”. "
                    "Sync Slack history or upload docs, then retry."
                ],
            },
            {
                "heading": "Open questions",
                "bullets": [
                    "What decisions or owners should this meeting cover?",
                ],
            },
        ]

    context_bullets: list[str] = []
    attribution_bullets: list[str] = []
    for c in citations:
        ex = excerpt(c.text, max_len=180)
        label = c.short_label()
        context_bullets.append(f"{ex} _(source: {label})_")
        if c.user:
            attribution_bullets.append(f"{c.user}: {ex}")

    sections: list[dict[str, Any]] = [
        {"heading": "Purpose", "bullets": [f"Discuss / align on: {topic}"]},
        {"heading": "Context from knowledge", "bullets": context_bullets},
    ]
    if attribution_bullets:
        sections.append(
            {"heading": "Who said what", "bullets": attribution_bullets}
        )
    sections.append(
        {
            "heading": "Suggested agenda",
            "bullets": [
                "Confirm latest status from the context above",
                "Decide owners / next steps",
                "Capture open questions",
            ],
        }
    )
    return sections


def _markdown_brief(
    topic: str,
    sections: list[dict[str, Any]],
    citations: list[KnowledgeCitation],
) -> str:
    lines = [f"# Meeting brief: {topic}", ""]
    for sec in sections:
        lines.append(f"## {sec['heading']}")
        for b in sec.get("bullets") or []:
            lines.append(f"- {b}")
        lines.append("")
    if citations:
        lines.append("## Sources")
        for c in citations:
            lines.append(f"- {c.short_label()} (score={c.score:.3f})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


__all__ = ["draft_meeting_brief"]

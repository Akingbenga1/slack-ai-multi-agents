"""MCP tool: ``draft_meeting_notes`` — notes from recent tenant context."""

from __future__ import annotations

from typing import Any

from api.app.retrieval.types import KnowledgeCitation
from mcp_server.tools.grounded import (
    SearchToolFn,
    excerpt,
    run_grounded_draft,
)


def draft_meeting_notes(
    *,
    client_id: str | None,
    topic: str,
    limit: int = 8,
    kind: str | None = None,
    channel: str | None = None,
    search_tool_fn: SearchToolFn | None = None,
) -> dict[str, Any]:
    """
    Build meeting notes from retrieved knowledge for one tenant.

    Deterministic (no LLM): decisions, action items, open questions from
    recent conversation/doc evidence. Agent compose (Sprint 16.4) may polish
    on Sonnet. Prefers Slack message hits when ``kind`` is unset.
    """
    subject = (topic or "").strip()
    if not subject:
        raise ValueError("topic must be non-empty")

    def outline_fn(citations: list[KnowledgeCitation]) -> dict[str, Any]:
        sections = _notes_sections(subject, citations)
        return {
            "topic": subject,
            "title": f"Meeting notes: {subject}",
            "sections": sections,
            "markdown": _markdown_notes(subject, sections, citations),
        }

    return run_grounded_draft(
        client_id=client_id,
        query=subject,
        outline_fn=outline_fn,
        limit=limit,
        kind=kind,
        channel=channel,
        search_tool_fn=search_tool_fn,
        prefer_kind="slack_message",
        empty_note=(
            "Insufficient tenant evidence — notes are a placeholder skeleton."
        ),
        evidence_note=(
            "Draft from retrieved evidence only; review before sharing."
        ),
    )


def _notes_sections(
    topic: str, citations: list[KnowledgeCitation]
) -> list[dict[str, Any]]:
    if not citations:
        return [
            {
                "heading": "Context",
                "bullets": [
                    f"No recent tenant context found for “{topic}”. "
                    "Sync Slack history or upload docs, then retry."
                ],
            },
            {
                "heading": "Decisions",
                "bullets": ["(none yet — no evidence)"],
            },
            {
                "heading": "Action items",
                "bullets": ["(none yet — no evidence)"],
            },
            {
                "heading": "Open questions",
                "bullets": [
                    "What decisions or follow-ups should these notes capture?",
                ],
            },
        ]

    context_bullets: list[str] = []
    action_bullets: list[str] = []
    for c in citations:
        ex = excerpt(c.text)
        label = c.short_label()
        speaker = c.user
        if speaker:
            context_bullets.append(f"{speaker}: {ex} _(source: {label})_")
            action_bullets.append(
                f"[ ] Follow up on “{excerpt(c.text, max_len=80)}” "
                f"— owner: {speaker}"
            )
        else:
            context_bullets.append(f"{ex} _(source: {label})_")
            action_bullets.append(
                f"[ ] Follow up on “{excerpt(c.text, max_len=80)}” "
                f"— owner: (unassigned)"
            )

    return [
        {
            "heading": "Context",
            "bullets": [f"Notes focused on: {topic}"] + context_bullets,
        },
        {
            "heading": "Decisions",
            "bullets": [
                "Confirm which of the context items above were decided "
                "(not invented — mark only what Evidence supports)."
            ],
        },
        {
            "heading": "Action items",
            "bullets": action_bullets,
        },
        {
            "heading": "Open questions",
            "bullets": [
                "Any unresolved points from the context above?",
            ],
        },
    ]


def _markdown_notes(
    topic: str,
    sections: list[dict[str, Any]],
    citations: list[KnowledgeCitation],
) -> str:
    lines = [f"# Meeting notes: {topic}", ""]
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


__all__ = ["draft_meeting_notes"]

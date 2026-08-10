"""MCP tool: ``draft_report`` — recurring digest over a time window."""

from __future__ import annotations

from typing import Any

from api.app.retrieval.types import KnowledgeCitation
from mcp_server.tools.grounded import (
    SearchToolFn,
    excerpt,
    run_grounded_draft,
)


def draft_report(
    *,
    client_id: str | None,
    window_label: str,
    limit: int = 8,
    kind: str | None = None,
    channel: str | None = None,
    topic: str | None = None,
    search_tool_fn: SearchToolFn | None = None,
) -> dict[str, Any]:
    """
    Build a recurring-report outline from retrieved knowledge for one tenant.

    Deterministic (no LLM): themes, decisions, open questions over the given
    window. Agent compose (Sprint 17.1) may polish on Sonnet. Prefers Slack
    message hits when ``kind`` is unset.
    """
    window = (window_label or "").strip()
    if not window:
        raise ValueError("window_label must be non-empty")

    subject = (topic or "").strip() or f"workspace activity ({window})"
    query = f"{subject} themes decisions updates {window}".strip()

    def outline_fn(citations: list[KnowledgeCitation]) -> dict[str, Any]:
        sections = _report_sections(window, subject, citations, channel=channel)
        return {
            "window_label": window,
            "topic": subject,
            "channel": channel,
            "title": f"Recurring report: {window}",
            "sections": sections,
            "markdown": _markdown_report(window, subject, sections, citations),
        }

    return run_grounded_draft(
        client_id=client_id,
        query=query,
        outline_fn=outline_fn,
        limit=limit,
        kind=kind,
        channel=channel,
        search_tool_fn=search_tool_fn,
        prefer_kind="slack_message",
        empty_note=(
            "Insufficient tenant evidence — report is a placeholder skeleton."
        ),
        evidence_note=(
            "Draft from retrieved evidence only; review before posting."
        ),
    )


def _report_sections(
    window: str,
    topic: str,
    citations: list[KnowledgeCitation],
    *,
    channel: str | None,
) -> list[dict[str, Any]]:
    scope = f"channel {channel}" if channel else "workspace"
    if not citations:
        return [
            {
                "heading": "Themes",
                "bullets": [
                    f"No tenant evidence found for {scope} over “{window}”. "
                    "Sync Slack history or upload docs, then retry."
                ],
            },
            {
                "heading": "Decisions",
                "bullets": ["(none yet — no evidence)"],
            },
            {
                "heading": "Open questions",
                "bullets": [
                    "What themes should this digest cover once evidence exists?",
                ],
            },
        ]

    theme_bullets: list[str] = []
    for c in citations:
        ex = excerpt(c.text)
        label = c.short_label()
        speaker = c.user
        if speaker:
            theme_bullets.append(f"{speaker}: {ex} _(source: {label})_")
        else:
            theme_bullets.append(f"{ex} _(source: {label})_")

    return [
        {
            "heading": "Themes",
            "bullets": [
                f"Digest window: {window} ({scope})",
                f"Focus: {topic}",
            ]
            + theme_bullets,
        },
        {
            "heading": "Decisions",
            "bullets": [
                "Confirm which of the themes above were decided "
                "(not invented — mark only what Evidence supports)."
            ],
        },
        {
            "heading": "Open questions",
            "bullets": [
                "Any unresolved points or follow-ups from the themes above?",
            ],
        },
    ]


def _markdown_report(
    window: str,
    topic: str,
    sections: list[dict[str, Any]],
    citations: list[KnowledgeCitation],
) -> str:
    lines = [f"# Recurring report: {window}", "", f"_Focus: {topic}_", ""]
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


__all__ = ["draft_report"]

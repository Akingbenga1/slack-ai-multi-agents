"""MCP tool: ``draft_report`` — recurring digest over a time window."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from api.app.qdrant.tenant import require_client_id
from api.app.retrieval.types import KnowledgeCitation, KnowledgeSearchResult
from mcp_server.serialize import citation_to_dict, search_result_to_dict
from mcp_server.tools.search import search_knowledge_tool

SearchToolFn = Callable[..., dict[str, Any]]


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
    cid = require_client_id(client_id)
    window = (window_label or "").strip()
    if not window:
        raise ValueError("window_label must be non-empty")

    subject = (topic or "").strip() or f"workspace activity ({window})"
    query = f"{subject} themes decisions updates {window}".strip()

    search = search_tool_fn or search_knowledge_tool
    search_kind = kind if kind is not None else "slack_message"
    raw = search(
        client_id=cid,
        query=query,
        limit=limit,
        kind=search_kind,
        channel=channel,
    )
    hits = raw.get("hits") or []
    citations = [_hit_as_citation(h) for h in hits if isinstance(h, dict)]

    if not citations and kind is None:
        raw = search(
            client_id=cid,
            query=query,
            limit=limit,
            kind=None,
            channel=channel,
        )
        hits = raw.get("hits") or []
        citations = [_hit_as_citation(h) for h in hits if isinstance(h, dict)]

    sections = _report_sections(window, subject, citations, channel=channel)
    markdown = _markdown_report(window, subject, sections, citations)

    return {
        "client_id": cid,
        "window_label": window,
        "topic": subject,
        "channel": channel,
        "title": f"Recurring report: {window}",
        "sections": sections,
        "markdown": markdown,
        "citations": [citation_to_dict(c) for c in citations],
        "retrieval": raw
        if "query" in raw
        else search_result_to_dict(
            KnowledgeSearchResult(
                client_id=cid, query=query, hits=citations, limit=limit
            )
        ),
        "hedged": len(citations) == 0,
        "note": (
            "Insufficient tenant evidence — report is a placeholder skeleton."
            if not citations
            else "Draft from retrieved evidence only; review before posting."
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
        excerpt = _excerpt(c.text)
        label = c.short_label()
        speaker = c.user
        if speaker:
            theme_bullets.append(f"{speaker}: {excerpt} _(source: {label})_")
        else:
            theme_bullets.append(f"{excerpt} _(source: {label})_")

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


def _excerpt(text: str, max_len: int = 160) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


__all__ = ["draft_report"]

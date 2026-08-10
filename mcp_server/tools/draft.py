"""MCP tool: ``draft_meeting_brief`` — outline from tenant knowledge."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from api.app.qdrant.tenant import require_client_id
from api.app.retrieval.types import KnowledgeCitation, KnowledgeSearchResult
from mcp_server.serialize import citation_to_dict, search_result_to_dict
from mcp_server.tools.search import search_knowledge_tool

SearchToolFn = Callable[..., dict[str, Any]]


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

    sections = _sections_from_citations(subject, citations)
    markdown = _markdown_brief(subject, sections, citations)

    return {
        "client_id": cid,
        "topic": subject,
        "title": f"Meeting brief: {subject}",
        "sections": sections,
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
            "Insufficient tenant evidence — brief is a placeholder skeleton."
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
        excerpt = _excerpt(c.text)
        label = c.short_label()
        context_bullets.append(f"{excerpt} _(source: {label})_")
        if c.user:
            attribution_bullets.append(f"{c.user}: {excerpt}")

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


def _excerpt(text: str, max_len: int = 180) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


__all__ = ["draft_meeting_brief"]

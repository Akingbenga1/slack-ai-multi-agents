"""MCP tool: ``draft_meeting_notes`` — notes from recent tenant context."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from api.app.qdrant.tenant import require_client_id
from api.app.retrieval.types import KnowledgeCitation, KnowledgeSearchResult
from mcp_server.serialize import citation_to_dict, search_result_to_dict
from mcp_server.tools.search import search_knowledge_tool

SearchToolFn = Callable[..., dict[str, Any]]


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
    cid = require_client_id(client_id)
    subject = (topic or "").strip()
    if not subject:
        raise ValueError("topic must be non-empty")

    search = search_tool_fn or search_knowledge_tool
    # Bias toward recent conversation context when caller does not filter kind
    search_kind = kind if kind is not None else "slack_message"
    raw = search(
        client_id=cid,
        query=subject,
        limit=limit,
        kind=search_kind,
        channel=channel,
    )
    hits = raw.get("hits") or []
    citations = [_hit_as_citation(h) for h in hits if isinstance(h, dict)]

    # If Slack-only returned nothing, widen to all kinds (docs + history)
    if not citations and kind is None:
        raw = search(
            client_id=cid,
            query=subject,
            limit=limit,
            kind=None,
            channel=channel,
        )
        hits = raw.get("hits") or []
        citations = [_hit_as_citation(h) for h in hits if isinstance(h, dict)]

    sections = _notes_sections(subject, citations)
    markdown = _markdown_notes(subject, sections, citations)

    return {
        "client_id": cid,
        "topic": subject,
        "title": f"Meeting notes: {subject}",
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
            "Insufficient tenant evidence — notes are a placeholder skeleton."
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
        excerpt = _excerpt(c.text)
        label = c.short_label()
        speaker = c.user
        if speaker:
            context_bullets.append(f"{speaker}: {excerpt} _(source: {label})_")
            action_bullets.append(
                f"[ ] Follow up on “{_excerpt(c.text, max_len=80)}” "
                f"— owner: {speaker}"
            )
        else:
            context_bullets.append(f"{excerpt} _(source: {label})_")
            action_bullets.append(
                f"[ ] Follow up on “{_excerpt(c.text, max_len=80)}” "
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


def _excerpt(text: str, max_len: int = 160) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


__all__ = ["draft_meeting_notes"]

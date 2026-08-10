"""Slack mrkdwn formatting for grounded agent replies (Sprint 14.2 / 16.5)."""

from __future__ import annotations

import re
from typing import Any, Sequence

# Max source lines appended under the answer
_MAX_SOURCES = 5

# ATX headings → Slack bold section labels
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
# Common Markdown list markers
_UL_RE = re.compile(r"^(\s*)([-*+])\s+")
# Markdown bold (** or __) — avoid matching single *
_MD_BOLD_RE = re.compile(r"(\*\*|__)(.+?)\1")


def source_label(chunk: dict[str, Any]) -> str:
    """Human-readable source hint from a retrieved chunk dict."""
    label = (chunk.get("label") or "").strip()
    if label:
        return label
    kind = (chunk.get("kind") or "source").strip()
    if kind == "document":
        name = chunk.get("filename") or chunk.get("title") or "document"
        return f"document {name}"
    if kind == "slack_message":
        parts = ["slack"]
        if chunk.get("channel"):
            parts.append(str(chunk["channel"]))
        if chunk.get("ts"):
            parts.append(f"ts={chunk['ts']}")
        return " ".join(parts)
    return kind


def format_sources(
    chunks: Sequence[dict[str, Any]] | None,
    *,
    max_sources: int = _MAX_SOURCES,
) -> str:
    """Build a Slack Sources block; empty string if nothing to show."""
    if not chunks:
        return ""
    seen: set[str] = set()
    lines: list[str] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        label = source_label(chunk)
        if label in seen:
            continue
        seen.add(label)
        lines.append(f"• {label}")
        if len(lines) >= max_sources:
            break
    if not lines:
        return ""
    return "*Sources:*\n" + "\n".join(lines)


def markdown_to_mrkdwn(text: str) -> str:
    """
    Light Markdown → Slack mrkdwn for structured meeting / coordination replies.

    Converts ATX headings, ``**bold**`` / ``__bold__``, and ``-``/``*`` bullets.
    Leaves existing Slack ``*bold*`` and numbered lists alone. Idempotent enough
    for already-mrkdwn answers (headings/bullets only change Markdown forms).
    """
    if not text:
        return text
    out_lines: list[str] = []
    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            title = m.group(2).strip()
            # Drop Markdown bold markers inside the heading title
            title = _MD_BOLD_RE.sub(r"\2", title)
            out_lines.append(f"*{title}*")
            continue
        line = _UL_RE.sub(r"\1• ", line)
        line = _MD_BOLD_RE.sub(r"*\2*", line)
        out_lines.append(line)
    return "\n".join(out_lines)


def format_slack_reply(
    answer: str,
    *,
    chunks: Sequence[dict[str, Any]] | None = None,
    hedge: bool = False,
) -> str:
    """
    Compose Slack message text: mrkdwn-normalised answer + optional Sources.

    Hedged answers omit Sources (no evidence to cite) and skip structure polish
    so the fixed hedge copy stays plain.
    """
    raw = (answer or "").strip() or "(no answer)"
    if hedge:
        return raw
    body = markdown_to_mrkdwn(raw).strip() or "(no answer)"
    sources = format_sources(chunks)
    if not sources:
        return body
    return f"{body}\n\n{sources}"

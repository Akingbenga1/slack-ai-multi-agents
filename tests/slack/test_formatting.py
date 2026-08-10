"""Slack citation + structured mrkdwn formatting (Sprint 14.2 / 16.5)."""

from __future__ import annotations

from api.app.slack.formatting import (
    format_slack_reply,
    format_sources,
    markdown_to_mrkdwn,
    source_label,
)


def test_format_slack_reply_with_sources():
    chunks = [
        {"label": "document refund.csv", "kind": "document", "filename": "refund.csv"},
        {"label": "slack C1 ts=1.0", "kind": "slack_message", "channel": "C1", "ts": "1.0"},
    ]
    text = format_slack_reply("Refunds within 30 days.", chunks=chunks, hedge=False)
    assert text.startswith("Refunds within 30 days.")
    assert "*Sources:*" in text
    assert "• document refund.csv" in text
    assert "• slack C1 ts=1.0" in text


def test_hedge_omits_sources():
    chunks = [{"label": "document x", "kind": "document"}]
    text = format_slack_reply("I don't have enough information…", chunks=chunks, hedge=True)
    assert "*Sources:*" not in text
    assert "enough information" in text


def test_dedupe_and_cap_sources():
    chunks = [
        {"label": "document a.csv"},
        {"label": "document a.csv"},
        {"label": "document b.csv"},
    ]
    block = format_sources(chunks, max_sources=1)
    assert block.count("•") == 1
    assert "a.csv" in block


def test_source_label_fallback():
    assert source_label({"kind": "document", "filename": "x.pdf"}) == "document x.pdf"
    assert "slack" in source_label({"kind": "slack_message", "channel": "C2", "ts": "9"})


def test_markdown_to_mrkdwn_meeting_structure():
    md = """# Meeting notes: beta

## Decisions
- Ship Friday
- **QA** owned by Bob

## Action items
1. Open checklist
* Follow up with design
"""
    out = markdown_to_mrkdwn(md)
    assert "*Meeting notes: beta*" in out
    assert "*Decisions*" in out
    assert "• Ship Friday" in out
    assert "*QA*" in out
    assert "1. Open checklist" in out
    assert "• Follow up with design" in out
    assert "#" not in out


def test_format_slack_reply_converts_structure():
    text = format_slack_reply(
        "## Context\n- Alice decided to ship",
        chunks=[{"label": "slack C3 ts=1"}],
        hedge=False,
    )
    assert text.startswith("*Context*")
    assert "• Alice decided to ship" in text
    assert "*Sources:*" in text


def test_hedge_skips_structure_polish():
    # Hedge path returns the body as-is (no Markdown conversion)
    text = format_slack_reply(
        "## would-be-heading\n- bullet",
        chunks=[{"label": "x"}],
        hedge=True,
    )
    assert text == "## would-be-heading\n- bullet"

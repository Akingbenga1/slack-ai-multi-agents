"""Slack mention/DM helpers: event filter, question extract, chat.postMessage."""

from __future__ import annotations

import re
from typing import Any, Optional

import httpx

from api.app.logging_config import get_logger

logger = get_logger("api.slack.echo")

_MENTION_RE = re.compile(r"<@[^>]+>\s*")


def should_echo(event: dict[str, Any]) -> bool:
    """True for human @mentions and DMs only; skip bots and channel chatter."""
    if event.get("bot_id") or event.get("subtype"):
        return False

    etype = event.get("type")
    if etype == "app_mention":
        return True

    if etype == "message":
        # message.im subscription delivers type=message with channel_type=im
        if event.get("channel_type") == "im":
            return True
        channel = event.get("channel") or ""
        if isinstance(channel, str) and channel.startswith("D"):
            return True

    return False


# Alias for Sprint 14 grounded reply path
should_reply = should_echo


def question_from_event(event: dict[str, Any]) -> str:
    """Strip bot @mentions; return the human question text."""
    raw = (event.get("text") or "").strip()
    cleaned = _MENTION_RE.sub("", raw).strip()
    return cleaned or "(empty message)"


def echo_text(event: dict[str, Any]) -> str:
    """Legacy Sprint 4 placeholder (tests / rollback). Prefer agent path."""
    return f"Echo: {question_from_event(event)}"


def conversation_id_for_event(event: dict[str, Any]) -> str:
    """
    Stable checkpointer conversation key.

    Mentions: channel + thread root (existing thread_ts or this message ts).
    DMs: DM channel id (one continuous conversation).
    """
    channel = str(event.get("channel") or "unknown")
    if event.get("type") == "app_mention":
        root = event.get("thread_ts") or event.get("ts") or "root"
        return f"{channel}:{root}"
    return channel


def reply_thread_ts(event: dict[str, Any]) -> Optional[str]:
    """Thread parent for channel mentions; None for DMs (top-level)."""
    if event.get("type") == "app_mention":
        ts = event.get("thread_ts") or event.get("ts")
        return str(ts) if ts else None
    return None


def post_message(
    *,
    bot_token: str,
    channel: str,
    text: str,
    thread_ts: Optional[str] = None,
) -> dict[str, Any]:
    """Post reply via chat.postMessage (install-store bot token)."""
    payload: dict[str, Any] = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts

    with httpx.Client(timeout=10.0) as client:
        resp = client.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    if not data.get("ok"):
        err = data.get("error") or "chat.postMessage failed"
        logger.warning("chat.postMessage failed error=%s", err)
        raise RuntimeError(f"Slack post failed: {err}")
    return data


# Back-compat name used by Sprint 4 echo path
post_echo = post_message

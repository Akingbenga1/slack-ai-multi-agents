"""Slack event filter / question helpers (Sprint 14.1)."""

from __future__ import annotations

from api.app.slack.echo import (
    conversation_id_for_event,
    echo_text,
    question_from_event,
    reply_thread_ts,
    should_echo,
    should_reply,
)


def test_should_reply_mention_and_dm():
    assert should_reply({"type": "app_mention", "text": "<@U1> hi"}) is True
    assert should_reply({"type": "message", "channel_type": "im", "text": "hi"}) is True
    assert should_reply({"type": "message", "channel": "D012", "text": "hi"}) is True
    assert should_echo is should_reply


def test_should_reply_skips_bots_and_channel_chatter():
    assert should_reply({"type": "app_mention", "bot_id": "B1", "text": "x"}) is False
    assert should_reply({"type": "message", "subtype": "message_changed"}) is False
    assert should_reply({"type": "message", "channel": "C012", "text": "hi"}) is False


def test_question_from_event_strips_mention():
    assert question_from_event({"text": "<@UBOT> refund policy?"}) == "refund policy?"
    assert question_from_event({"text": "   "}) == "(empty message)"
    assert echo_text({"text": "<@U> hi"}) == "Echo: hi"


def test_conversation_and_thread_for_mention():
    event = {
        "type": "app_mention",
        "channel": "C1",
        "ts": "100.1",
        "text": "<@U> hi",
    }
    assert conversation_id_for_event(event) == "C1:100.1"
    assert reply_thread_ts(event) == "100.1"

    threaded = {**event, "thread_ts": "99.0", "ts": "100.1"}
    assert conversation_id_for_event(threaded) == "C1:99.0"
    assert reply_thread_ts(threaded) == "99.0"


def test_dm_conversation_is_channel():
    event = {"type": "message", "channel_type": "im", "channel": "D9", "ts": "1.0"}
    assert conversation_id_for_event(event) == "D9"
    assert reply_thread_ts(event) is None

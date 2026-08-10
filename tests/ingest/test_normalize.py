"""Unit tests for shared Slack message normalizer (Task 7.1)."""

from api.app.ingest import NormalizedMessage, SourceFormat, normalize_slack_message


def test_normalize_happy_path():
    msg = normalize_slack_message(
        {
            "type": "message",
            "user": "U111",
            "text": "Ship the launch checklist",
            "ts": "1710000000.000100",
            "thread_ts": "1710000000.000050",
            "channel": "C111",
        },
        source_format=SourceFormat.JSON,
    )
    assert msg is not None
    assert msg == NormalizedMessage(
        channel="C111",
        ts="1710000000.000100",
        user="U111",
        text="Ship the launch checklist",
        thread_ts="1710000000.000050",
        source_format=SourceFormat.JSON,
    )
    assert msg.content_key == "C111:1710000000.000100"


def test_normalize_channel_override():
    msg = normalize_slack_message(
        {"type": "message", "user": "U1", "text": "hi", "ts": "1.1"},
        channel="C999",
        source_format="slack_export",
    )
    assert msg is not None
    assert msg.channel == "C999"
    assert msg.source_format is SourceFormat.SLACK_EXPORT


def test_normalize_skips_join_and_empty():
    assert (
        normalize_slack_message(
            {
                "type": "message",
                "subtype": "channel_join",
                "user": "U1",
                "text": "<@U1> has joined",
                "ts": "1.1",
                "channel": "C1",
            },
            source_format=SourceFormat.JSON,
        )
        is None
    )
    assert (
        normalize_slack_message(
            {"type": "message", "text": "  ", "ts": "1.1", "channel": "C1"},
            source_format=SourceFormat.JSON,
        )
        is None
    )


def test_normalize_clears_self_thread_ts():
    msg = normalize_slack_message(
        {
            "type": "message",
            "text": "parent",
            "ts": "2.2",
            "thread_ts": "2.2",
            "channel": "C1",
            "user": "U1",
        },
        source_format=SourceFormat.WEB_API,
    )
    assert msg is not None
    assert msg.thread_ts is None

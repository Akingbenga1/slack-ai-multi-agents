"""Unit tests for JSON / NDJSON message dump parsers (Task 7.3)."""

import json

import pytest

from api.app.ingest.parsers.json_dump import (
    MissingChannelError,
    iter_json_messages,
    iter_ndjson_messages,
)
from api.app.ingest.schema import SourceFormat


def test_json_conversations_history_shape():
    payload = {
        "channel": "CABC",
        "messages": [
            {
                "type": "message",
                "user": "U1",
                "text": "From history dump",
                "ts": "1.1",
            }
        ],
    }
    msgs = list(iter_json_messages(json.dumps(payload)))
    assert len(msgs) == 1
    assert msgs[0].channel == "CABC"
    assert msgs[0].source_format is SourceFormat.JSON


def test_json_array_requires_channel_or_override():
    arr = json.dumps([{"type": "message", "user": "U1", "text": "x", "ts": "1.1"}])
    with pytest.raises(MissingChannelError):
        list(iter_json_messages(arr))
    msgs = list(iter_json_messages(arr, channel="COVER"))
    assert msgs[0].channel == "COVER"


def test_json_array_per_message_channel():
    arr = json.dumps(
        [
            {
                "type": "message",
                "channel": "C1",
                "user": "U1",
                "text": "a",
                "ts": "1.1",
            },
            {
                "type": "message",
                "channel_id": "C2",
                "user": "U2",
                "text": "b",
                "ts": "2.2",
            },
        ]
    )
    msgs = list(iter_json_messages(arr))
    assert [m.channel for m in msgs] == ["C1", "C2"]


def test_ndjson_lines():
    text = "\n".join(
        [
            '{"type":"message","channel":"C1","user":"U1","text":"one","ts":"1.1"}',
            "",
            '{"channel":"C2","messages":[{"type":"message","user":"U2","text":"two","ts":"2.2"}]}',
            '{"type":"message","user":"U3","text":"no channel","ts":"3.3"}',
        ]
    )
    msgs = list(iter_ndjson_messages(text))
    assert len(msgs) == 2
    assert msgs[0].text == "one"
    assert msgs[0].source_format is SourceFormat.NDJSON
    assert msgs[1].channel == "C2"
    assert msgs[1].text == "two"


def test_ndjson_channel_override():
    text = '{"type":"message","user":"U1","text":"hi","ts":"1.1"}\n'
    msgs = list(iter_ndjson_messages(text, channel="CFIX"))
    assert len(msgs) == 1
    assert msgs[0].channel == "CFIX"

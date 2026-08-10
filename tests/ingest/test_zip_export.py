"""Unit tests for Slack export ZIP parser (Task 7.2)."""

import io
import json
import zipfile

from api.app.ingest.parsers import iter_slack_export_zip
from api.app.ingest.schema import SourceFormat


def _build_export_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "channels.json",
            json.dumps([{"id": "CGENERAL", "name": "general"}]),
        )
        zf.writestr(
            "general/2024-01-15.json",
            json.dumps(
                [
                    {
                        "type": "message",
                        "user": "U1",
                        "text": "Decision: use Qdrant",
                        "ts": "1705300000.000100",
                    },
                    {
                        "type": "message",
                        "subtype": "channel_join",
                        "user": "U2",
                        "text": "<@U2> has joined the channel",
                        "ts": "1705300000.000200",
                    },
                    {
                        "type": "message",
                        "user": "U3",
                        "text": "Reply in thread",
                        "ts": "1705300000.000300",
                        "thread_ts": "1705300000.000100",
                    },
                ]
            ),
        )
        zf.writestr(
            "random/2024-01-16.json",
            json.dumps(
                [
                    {
                        "type": "message",
                        "user": "U4",
                        "text": "Unmapped channel folder",
                        "ts": "1705400000.000100",
                    }
                ]
            ),
        )
    return buf.getvalue()


def test_iter_slack_export_zip_resolves_channel_id():
    raw = _build_export_zip()
    msgs = list(iter_slack_export_zip(io.BytesIO(raw)))
    assert len(msgs) == 3
    assert msgs[0].channel == "CGENERAL"
    assert msgs[0].text == "Decision: use Qdrant"
    assert msgs[0].source_format is SourceFormat.SLACK_EXPORT
    assert msgs[1].thread_ts == "1705300000.000100"
    # random/ not in channels.json → folder name kept
    assert msgs[2].channel == "random"
    assert msgs[2].text == "Unmapped channel folder"

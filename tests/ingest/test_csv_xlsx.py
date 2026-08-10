"""Unit tests for CSV / Excel message dump parsers (Task 7.4)."""

import io

import openpyxl
import pytest

from api.app.ingest.parsers.csv_xlsx import (
    default_column_map,
    iter_csv_messages,
    iter_xlsx_messages,
)
from api.app.ingest.parsers.json_dump import MissingChannelError
from api.app.ingest.schema import SourceFormat


def test_csv_default_headers():
    csv = (
        "channel,ts,user,text,thread_ts\n"
        "C1,1.1,U1,hello,\n"
        "C1,2.2,U2,reply,1.1\n"
    )
    msgs = list(iter_csv_messages(csv))
    assert len(msgs) == 2
    assert msgs[0].channel == "C1"
    assert msgs[0].text == "hello"
    assert msgs[0].source_format is SourceFormat.CSV
    assert msgs[1].thread_ts == "1.1"


def test_csv_aliases_and_channel_override():
    csv = "message_ts,author,message\n1.1,U9,aliased body\n"
    with pytest.raises(MissingChannelError):
        list(iter_csv_messages(csv))
    msgs = list(iter_csv_messages(csv, channel="COVER"))
    assert len(msgs) == 1
    assert msgs[0].channel == "COVER"
    assert msgs[0].user == "U9"
    assert msgs[0].text == "aliased body"
    assert msgs[0].ts == "1.1"


def test_csv_column_map_override():
    csv = "ch,stamp,who,body\nC9,9.9,U1,mapped\n"
    msgs = list(
        iter_csv_messages(
            csv,
            column_map={
                "channel": "ch",
                "ts": "stamp",
                "user": "who",
                "text": "body",
            },
        )
    )
    assert len(msgs) == 1
    assert msgs[0].channel == "C9"
    assert msgs[0].text == "mapped"


def test_csv_skips_empty_text():
    csv = "channel,ts,user,text\nC1,1.1,U1,\nC1,2.2,U2,ok\n"
    msgs = list(iter_csv_messages(csv))
    assert len(msgs) == 1
    assert msgs[0].text == "ok"


def test_xlsx_default_headers():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["channel_id", "ts", "user_id", "text"])
    ws.append(["CX", "3.3", "UX", "from excel"])
    buf = io.BytesIO()
    wb.save(buf)
    msgs = list(iter_xlsx_messages(buf.getvalue()))
    assert len(msgs) == 1
    assert msgs[0].channel == "CX"
    assert msgs[0].source_format is SourceFormat.XLSX
    assert msgs[0].text == "from excel"


def test_default_column_map_keys():
    m = default_column_map()
    assert set(m) >= {"channel", "ts", "user", "text", "thread_ts"}

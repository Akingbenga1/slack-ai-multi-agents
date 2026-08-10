# Slack history file ingest

Bootstrap dumps are normalized to a shared message schema, then chunked → TEI → Qdrant (tenant-scoped).

## Shared schema (`api/app/ingest`)

Fields: `channel`, `ts`, `user`, `text`, `thread_ts`, `source_format`.

`source_format` values: `slack_export` | `json` | `ndjson` | `csv` | `xlsx` | `web_api`.

```python
from api.app.ingest import normalize_slack_message, SourceFormat, ingest_messages
from api.app.ingest.parsers import (
    iter_slack_export_zip,
    iter_json_messages,
    iter_ndjson_messages,
    iter_csv_messages,
    iter_xlsx_messages,
)

msgs = list(iter_slack_export_zip("path/to/export.zip"))
msgs = list(iter_json_messages("dump.json", channel="C0123"))  # if file has no channel
msgs = list(iter_ndjson_messages(open("dump.ndjson", encoding="utf-8")))
msgs = list(iter_csv_messages("dump.csv", channel="C0123"))
msgs = list(iter_xlsx_messages("dump.xlsx"))

result = ingest_messages(client_id="…-tenant-uuid-…", messages=msgs)
```

## Formats

| Format | Parser | Notes |
| ------ | ------ | ----- |
| Slack export ZIP | `iter_slack_export_zip` | Uses `channels.json` name→id; day files `channel/YYYY-MM-DD.json` |
| JSON | `iter_json_messages` | Array of messages, or `{channel, messages}` (history-style) |
| NDJSON | `iter_ndjson_messages` | One object per line; missing channel skips the line unless `channel=` set |
| CSV | `iter_csv_messages` | Header aliases or `column_map=` (logical → header) |
| Excel | `iter_xlsx_messages` | Same mapping; first sheet by default (`sheet_name=`) |
| Live Web API | Sprint 9 | Same schema, `source_format=web_api` — see `docs/slack-web-api.md` |

Flat JSON / CSV / XLSX **without** a channel column require `channel=` or raise `MissingChannelError`.

### CSV / Excel column mapping

Default aliases (case-insensitive): `channel`/`channel_id`, `ts`/`timestamp`/`message_ts`, `user`/`user_id`/`author`, `text`/`message`/`body`, `thread_ts`/`parent_ts`.

```python
list(iter_csv_messages(path, column_map={"channel": "ch", "ts": "stamp", "text": "body"}))
```

## Pipeline (chunk → TEI → Qdrant)

- Chunk text includes `channel` / `user` / `ts` metadata prefix.
- Point ids are deterministic uuid5(`client_id|channel|ts|chunk_index`) for idempotent re-ingest.
- Payload includes `content_hash`, `content_key`, `kind=slack_message`, plus message fields.
- Upsert/search always require `client_id` (Sprint 6 fail-closed helpers).

### CLI

```bash
uv run python scripts/ingest_slack_history.py \
  --client-id aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa \
  --format json \
  --path data/sample_history.json \
  --query "onboarding checklist"
```

Supported `--format`: `zip` | `json` | `ndjson` | `csv` | `xlsx`.

## Tests

```bash
uv run pytest tests/ingest -q
```

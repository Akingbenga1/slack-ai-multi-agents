# Task 7.3 — Raw JSON / NDJSON parser

## Steps

- [x] Parse API-dump shaped JSON: message array, or `{channel, messages}` / list of such
- [x] Parse NDJSON (one message object per line)
- [x] Channel from object field or explicit override
- [x] Yield normalized messages with `source_format=json` or `ndjson`
- [x] Light fixture tests

## Acceptance criteria

- [x] JSON array / conversations.history-style dump → shared schema
- [x] NDJSON lines → shared schema
- [x] Missing channel without override → skip or clear error (documented)

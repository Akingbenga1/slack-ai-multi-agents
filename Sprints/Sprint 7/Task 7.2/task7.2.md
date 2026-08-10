# Task 7.2 — Export ZIP parser

## Steps

- [x] Parse Slack workspace export ZIP layout (channels.json + per-channel day JSON)
- [x] Resolve channel name → id when `channels.json` present
- [x] Yield normalized messages with `source_format=slack_export`
- [x] Accept path or file-like ZIP; light fixture test

## Acceptance criteria

- [x] Sample export ZIP → iterable of shared schema messages
- [x] Channel identity preferred as Slack channel id when known
- [x] Non-message / empty text rows skipped via normalizer

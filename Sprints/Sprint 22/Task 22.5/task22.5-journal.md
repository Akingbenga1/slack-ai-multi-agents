# Task 22.5 journal

## Status

`completed`

## Summary

Hardened gitignore for secrets/data and added basic transient retries across Slack, Anthropic, TEI, and Qdrant.

## Acceptance criteria checklist

- [x] Gitignore secrets/data
- [x] Basic retries on outbound failures

## Decision log

- Anthropic uses SDK built-in `max_retries=3`.
- TEI/Qdrant share `call_with_retries`; Slack extends existing 429 loop to 5xx/transport.

## Needs human

None for this task (no live credential rotation required in-repo).

## Files changed

- `.gitignore`, `docs/security.md`, `README.md`
- `api/app/http_retry.py`, `api/app/tei/client.py`, `api/app/qdrant/vectors.py`, `api/app/slack/client.py`, `api/app/agent/llm.py`
- `tests/test_http_retry.py`, `tests/slack/test_client.py`

## Resume notes

Sprint 22 complete. Next deferred theme is Sprint 23 (Slack file actions) unless product re-prioritises.

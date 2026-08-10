# Task 7.5 journal

## Status

`completed`

## Summary

`chunk_messages` + `ingest_messages` embed via TEI and upsert into Qdrant with deterministic uuid5 point ids (`client_id|channel|ts|chunk_index`). CLI `scripts/ingest_slack_history.py` loads ZIP/JSON/NDJSON/CSV/XLSX for one tenant; optional `--query` smoke search. Sample dump searchable; re-ingest keeps the same point count (idempotent).

## Acceptance criteria checklist

- [x] Sample dump searchable for one tenant — done (CLI smoke)
- [x] Idempotent re-ingest — done (uuid5 ids; second run still 3 points)
- [x] Missing client_id fail-closed — done (reuses Sprint 6 helpers)

## Decision log

- Embed text prefixes `channel` / `user` / `ts` for retrieval context.
- Idempotency keyed by channel+ts+chunk_index (payload also stores `content_hash`).
- CLI rather than API job for Sprint 7 exit (upload API is Sprint 8).

## Needs human

None.

## Files changed

- `api/app/ingest/chunk.py`, `pipeline.py`, `__init__.py`
- `scripts/ingest_slack_history.py`
- `tests/ingest/test_pipeline.py`
- `docs/slack-history-ingest.md`, `docs/qdrant-tei.md`, `README.md`

## Resume notes

Sprint 7 complete. Next: **Continue Sprint 8 from Task 8.1**.

## Open questions

None.

## Smoke test results

```
uv run pytest tests/ingest -q  → 19 passed
uv run python scripts/ingest_slack_history.py \
  --client-id aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa \
  --format json --path data/sample_history.json \
  --query "onboarding checklist"
→ ingested messages=3 chunks=3; top hit = sample onboarding text; ingest_ok
(re-run) → same 3 points (idempotent)
```

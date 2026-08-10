# Task 6.2 journal

## Status

`completed`

## Summary

Added `api/app/tei/TeiClient` calling Compose TEI `POST /embed` with `truncate=true`. Settings expose `embedding_model_id` / `embedding_dim`; embed output validated against dim.

## Acceptance criteria checklist

- [x] Model id in settings — done (`EMBEDDING_MODEL_ID`)
- [x] Embed via TEI — done
- [x] Dim matches — done (384)

## Decision log

- Native TEI `/embed` (not OpenAI-compat `/v1/embeddings`).
- Default truncate on to avoid hard failures on long inputs later.

## Needs human

None.

## Files changed

- `api/app/tei/client.py`, `api/app/tei/__init__.py`
- `api/app/settings.py`, `.env.example`

## Resume notes

Continue Task 6.3 isolation smoke (same batch).

## Open questions

None.

## Smoke test results

- `/info` → `BAAI/bge-small-en-v1.5`; embed dim 384

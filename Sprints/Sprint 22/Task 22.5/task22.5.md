# Task 22.5 — Security hygiene

## Steps

- [x] Harden `.gitignore` for `.env*`, `secrets/`, keys, credentials, `data/`
- [x] Shared `api.app.http_retry` helper
- [x] Slack: retry 5xx + transport errors (429 already present)
- [x] Anthropic: SDK `max_retries`
- [x] TEI + Qdrant upsert/search: transient retries
- [x] `docs/security.md` + tests

## Acceptance criteria

- [x] Secrets/local data patterns are gitignored
- [x] Slack / Anthropic / TEI / Qdrant have basic retries on transient failures

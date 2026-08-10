# Security hygiene (Sprint 22.5)

## Secrets & local data

Never commit:

| Path / pattern | Why |
| -------------- | --- |
| `.env`, `.env.*` (except `.env.example`) | API keys, Slack, Stripe |
| `secrets/`, `*.pem`, `*.key`, `credentials.json` | Certs / service accounts |
| `data/` | Uploads, history dumps, corpora |

Copy `.env.example` → `.env` locally. Operator bring-up: `docs/operator.md`.

## Transient retries

Outbound clients retry briefly on rate limits / 5xx / transport errors:

| Client | Behaviour |
| ------ | --------- |
| Slack Web API | 429 (`Retry-After`), HTTP 5xx, connect/timeout — exponential backoff |
| Anthropic | SDK `max_retries=3` |
| TEI | 429 / 5xx / transport via `api.app.http_retry` |
| Qdrant upsert/search | Transient transport / unavailable via `http_retry` |

Shared helper: `api.app.http_retry.call_with_retries`.

# Task 12.1 — Per-tenant rate limit at gateway

## Steps

- [x] Settings: `RATE_LIMIT_RPM` (+ enable flag)
- [x] Redis fixed-window counter keyed by `client_id` (per minute)
- [x] Gateway middleware: enforce when `X-Client-Id` / tenant context present
- [x] Helper for routes that resolve tenant later (e.g. Slack Events)
- [x] Exempt health, docs, Stripe webhooks
- [x] 429 + `Retry-After` / rate-limit headers when over limit
- [x] Light unit tests + docs

## Acceptance criteria

- [x] Requests for a tenant beyond RPM are blocked (HTTP 429)
- [x] Tenants are isolated (counters keyed by `client_id`)
- [x] Missing Redis fails open (logged); missing `client_id` skips limit

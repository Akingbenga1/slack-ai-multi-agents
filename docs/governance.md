# Governance (rate limits, budgets, usage)

Per-tenant controls at the FastAPI gateway and shared helpers for workers / Slack.

## Rate limit (Task 12.1)

Fixed-window **requests per minute (RPM)** keyed by `client_id` in Redis.

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `RATE_LIMIT_ENABLED` | `true` | Master switch |
| `RATE_LIMIT_RPM` | `60` | Max requests per tenant per UTC minute window |
| `REDIS_URL` | Compose Redis | Counter store |

### Enforcement

1. **Middleware** (`TenantRateLimitMiddleware`) — when `X-Client-Id` is present (after `TenantContextMiddleware`). Returns **HTTP 429** with `Retry-After`, `X-RateLimit-*` headers.
2. **Slack Events** — after install → tenant resolve, same counter. Returns **200** `{ok, rate_limited}` (not 429) so Slack does not retry-storm.

### Exempt paths

`/health`, `/docs`, `/redoc`, `/openapi.json`, `/billing/webhooks/*`

### Behavior notes

- No `client_id` → skip (not counted).
- Redis errors → **fail open** (request allowed; logged).
- Tenants are isolated: key shape `rl:rpm:{client_id}:{window_start}`.

### Helper

```python
from api.app.governance.rate_limit import check_tenant_rate_limit

decision = check_tenant_rate_limit(client_id)
if not decision.allowed:
    ...
```

## Budgets (Task 12.2)

Active plan entitlements include numeric caps (set on activate / cleared on deactivate):

| Key | Default (active) | Window |
| --- | ---------------- | ------ |
| `tokens_daily` | 100_000 | UTC day |
| `tokens_monthly` | 2_000_000 | UTC month |
| `jobs_daily` | 50 | UTC day |

```python
from api.app.governance.budgets import check_budget, require_budget

d = check_budget(db, tenant_id, "jobs", units=1)
require_budget(db, tenant_id, "jobs")  # HTTP 403 if over
```

- Job enqueue: `/jobs/heartbeat` uses budget only; `/jobs/slack-history-sync` and `/jobs/recurring-report` also require an active plan entitlement (`sync` / `agent`) via `require_entitlement`.
- Upload ingest enqueue (`POST /uploads`) requires `ingest` + `require_budget(..., require_active_plan=True)`.
- Inactive plan: budget check **allows** by default (`reason=plan_inactive`) unless `require_active_plan=True`; product paths that spend jobs now pass `require_active_plan=True`.
- Slack agent path posts a clear denial when unpaid (Sprint 14.3).
- Beat due-lists (`list_tenants_for_scheduled_slack_sync` / `list_tenants_for_scheduled_reports`) skip tenants lacking `sync` / `agent`.
- Over cap → **403** `{ detail: budget_exceeded, resource, limit, used, remaining, window }` on HTTP APIs; Slack posts a budget denial instead of running LangGraph.


## Usage events (Task 12.3)

Table `usage_events` (tenant_id, event_type, units, meta, created_at).

| event_type | When |
| ---------- | ---- |
| `slack_mention` | Slack mention/DM agent reply posted (not on entitlement deny) |
| `sync_run` | Live Slack history sync succeeded |
| `ingest` | Upload ingest succeeded |
| `job` | Heartbeat (and generic jobs) succeeded |
| `llm_tokens` | LangGraph compose (Anthropic or stub token estimate) |
| `report_post` | Recurring report channel posts (Sprint 17) |

```python
from api.app.governance.usage import record_usage, EVENT_LLM_TOKENS

record_usage(db, tenant_id, EVENT_LLM_TOKENS, units=1200, meta={"model": "haiku"})
```

Budget sums: `jobs_daily` ← `job`/`sync_run`/`ingest`/`report_post`/`file_job`/`pdf_generate`/`file_rename`; token budgets ← `llm_tokens`.

## Usage summary API (Task 12.4)

Authenticated aggregates for the org portal logs/usage page.

```http
GET /usage/summary?window=day|month
Authorization: Bearer <jwt>
X-Client-Id: <tenant_id>   # optional if JWT already has tenant_id
```

Response shape:

| Field | Meaning |
| ----- | ------- |
| `by_event_type[]` | `event_type`, `event_count`, `units` for the UTC window |
| `totals` | Sum of counts / units |
| `budgets[]` | `tokens_daily` / `tokens_monthly` / `jobs_daily` used / limit / remaining |
| `plan_active` | Whether plan currently grants budgets |

```python
from api.app.governance.summary import build_usage_summary

payload = build_usage_summary(db, tenant_id, window="day")
```

Portal: `/app/usage` (Next.js) calls this endpoint plus recent event/job logs.

## Usage event + job logs (Task 20.2)

```http
GET /usage/events?event_type=slack_mention&limit=50
GET /usage/jobs?status=failed&limit=50
Authorization: Bearer <jwt>
```

| Endpoint | Purpose |
| -------- | ------- |
| `/usage/events` | Newest `usage_events` (filter by `event_type`: mentions, `llm_tokens`, jobs, …) |
| `/usage/jobs` | Newest `jobs` rows; `status=failed` for errors |

Helpers: `list_usage_events` / `list_jobs` in `api.app.governance.logs`.


# Org portal (Sprint 19–20)

Next.js self-serve surfaces for org admins (`admin@example.com` / `admin123`).

## Routes

| Path | Purpose |
| ---- | ------- |
| `/app` | Portal home |
| `/app/agent` | Agent name, system prompt, channel allowlist, job schedules (OR-03 / OR-04) |
| `/app/knowledge` | Uploads, ingest job status, Slack sync trigger/status (OR-05 / OR-06) |
| `/app/billing` | Stripe Checkout + Customer Portal (OR-02) |
| `/app/usage` | Usage summary + recent logs (OR-07) |
| `/app/slack` | Connect Slack workspace + connection status (OR-08) |
| `/app/t/[tenantId]` | Tenant-scoped entry — **403 UI** if id ≠ session tenant (OR-09) |

## APIs used

| UI | API |
| -- | --- |
| Agent details | `GET` / `PATCH /agent/config` |
| Schedules (sync + report) | `GET` / `PATCH /agent/schedules` |
| Slack sync schedule (legacy) | `GET` / `PATCH /jobs/slack-history-sync/schedule` |
| Recurring report schedule (legacy) | `GET` / `PATCH /jobs/recurring-report/schedule` |
| Upload | `POST /uploads` |
| Ingest status | `GET /uploads/jobs`, `GET /uploads/status/{upload_id}` |
| Live sync | `GET /jobs/slack-history-sync/status`, `POST /jobs/slack-history-sync` |
| Billing | `GET /billing/customers/me`, `POST /billing/checkout-session`, `POST /billing/portal-session` |
| Usage / logs | `GET /usage/summary`, `GET /usage/events`, `GET /usage/jobs` |
| Slack connect | `GET /slack/connection`, install via `GET /slack/install?tenant_id=` |

Display name is stored in `agent_configs.extra.display_name` (row key stays `name=default` for schedule lookups). `system_prompt` is prepended as an org overlay in compose when set.

Allowlist shape: `{"channels": ["C…"]}`. Empty = unrestricted (stored); Slack enforcement can tighten later.

## Billing (OR-02)

- `/app/billing` starts Checkout and opens the Stripe Customer Portal (session tenant only).
- Success/cancel return to `/app/billing?checkout=success|cancel`; the page polls plan status until the webhook activates (or times out).
- Full Stripe env / webhook notes: `docs/billing.md`.

## Tenant scoping (OR-09)

- Portal pages pass **session** `tenantId` only (`web/lib/tenant.ts` → `sessionTenantId`).
- Client fetches use `apiAuthHeaders(token, sessionTenant)` — never a foreign id from the URL.
- Upload widget no longer posts form `tenant_id` (JWT / `X-Client-Id` only).
- Middleware strips `?tenant_id=` / `?client_id=` / `?tenant=` when they disagree with the session.
- `/app/t/{other}` shows access denied for org admins.
- API still enforces `require_tenant_access` (403 on cross-tenant).

## Empty / error states (Sprint 20.4)

Portal home shows banners for:

| Condition | CTA |
| --------- | --- |
| Plan inactive / no billing customer | `/app/billing` |
| Slack not connected | `/app/slack` |
| Latest Slack sync failed | `/app/knowledge` |

Knowledge sync panel also surfaces disconnected Slack and last failure inline. Billing and Slack pages keep their own unpaid / disconnected copy.

## Smoke

```bash
# API
uv run pytest tests/agent/test_config_api.py tests/uploads/test_ingest_status.py tests/billing tests/governance -q

# Portal (API + seed + web)
# Sign in as admin@example.com → /app/billing, /app/usage, /app/slack
```

Platform owner surfaces: `docs/admin-portal.md` (`owner@example.com` → `/admin`).

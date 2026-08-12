# Org portal (Sprint 19–20)

Next.js self-serve surfaces for org admins. Demo seed (`admin@example.com` / `admin123`) still works; **new orgs can register at `/signup`** without that seed or a platform-owner ticket (Sprint 31 / `OR-01`).

## Routes

| Path | Purpose |
| ---- | ------- |
| `/signup` | Public org registration — creates tenant + admin, then session into `/app` |
| `/login` | Sign-in only (existing users) |
| `/invite` | Create / accept org-admin magic-link invites (no SMTP; copy `{WEB_APP_URL}/invite?token=…`) |
| `/app` | Portal home |
| `/app/agent` | Agent name, system prompt, channel allowlist, job schedules (OR-03 / OR-04) |
| `/app/knowledge` | Uploads, ingest job status, Slack sync trigger/status (OR-05 / OR-06) |
| `/app/billing` | Pay / manage subscription (OR-02) |
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
| Signup | `POST /auth/signup` (public) |
| Invites | `POST` / `GET /auth/invites` (org admin); `GET /auth/invites/preview`, `POST /auth/invites/accept` (public token) |

Display name is stored in `agent_configs.extra.display_name` (row key stays `name=default` for schedule lookups). `system_prompt` is prepended as an org overlay in compose when set.

Allowlist shape: `{"channels": ["C…"]}`. Empty = unrestricted (stored); Slack enforcement can tighten later.

## Signup and invites (Sprint 31)

- `/signup` calls `POST /auth/signup` then NextAuth credentials so the org rep lands in `/app`. Demo seed is optional; `DEMO_ACTIVATE_PLAN` is **not** required (self-signup plan starts inactive).
- Sign-in uses `IDENTITY_PROVIDER` (demo default `credentials`) on both API (`POST /auth/token` → `IdentityProvider.verify`) and NextAuth (`web/lib/auth.ts` factory). No OIDC/SAML keys this sprint.
- No extra env keys for signup itself — signup reuses `JWT_SECRET`, `WEB_APP_URL`, and NextAuth (`NEXTAUTH_URL` / `NEXTAUTH_SECRET`).
- `/invite` creates a copyable magic-link `{WEB_APP_URL}/invite?token=…`. The API stores only an HMAC-SHA256 of the token keyed with `JWT_SECRET`. SMTP is out of scope.
- Accepting an invite joins the **existing** tenant as `org_admin`; it does not create a second organisation.
- Slack “start onboarding” / MCP `start_onboarding` is the Sprint 18 **process stub** (`docs/onboarding.md`). It is unchanged and is **not** tenant registration.

## Billing (OR-02)

- `/app/billing` talks **pay / manage subscription** (session tenant only). Checkout and portal sessions go through the configured `PAYMENT_PROVIDER` adapter (`docs/billing.md`).
- Success/cancel return to `/app/billing?checkout=success|cancel`; the page polls plan status until payment confirmation activates the plan (or times out).
- Adapter secrets (e.g. Stripe keys when `PAYMENT_PROVIDER=stripe`): `docs/billing.md`.

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
# Or register at /signup (no demo credentials required)
```

Platform owner surfaces: `docs/admin-portal.md` (`owner@example.com` → `/admin`).

# Platform admin portal (Sprint 21)

Next.js `/admin` for `platform_owner` (`owner@example.com` / `owner123`).

## Routes

| Path | Purpose |
| ---- | ------- |
| `/admin` | Admin home |
| `/admin/tenants` | Tenant list — plan, Slack, last sync (PO-01 / PO-25) |
| `/admin/tenants/[id]` | Tenant detail — billing/plan vs suspend vs Stripe, plan override, budget override, audit (21.3 / 32.2) |
| `/admin/health` | Compose deep health + job/usage error rates (PO-13) |

## APIs

| Method | Path | Notes |
| ------ | ---- | ----- |
| `GET` | `/admin/tenants` | Owner only — list summaries |
| `POST` | `/admin/tenants` | Create org (slug, name, admin email/password, optional `activate_plan`) — PO-04 |
| `GET` | `/admin/tenants/{id}` | Detail + embedded sync status |
| `GET` | `/admin/health?hours=24` | Deep health + failed jobs / usage |
| `PATCH` | `/admin/tenants/{id}/status` | `{ "status": "active" \| "suspended" }` + audit |
| `PATCH` | `/admin/tenants/{id}/plan` | `{ "plan_status": "active" \| "inactive", "reason": "…" }` — post-create payment waiver / restore Stripe control (Sprint 32) |
| `PATCH` | `/admin/tenants/{id}/budgets` | Override `tokens_daily` / `tokens_monthly` / `jobs_daily` + audit |
| `GET` | `/admin/audit-logs?tenant_id=&limit=` | Recent support actions |

`POST /admin/tenants` creates tenant + org admin membership + billing row + default agent config, audited as `tenant.created`. If `admin_password` is omitted, a password is generated and returned once.

Public `/signup` (Sprint 31) does **not** replace this path — the platform owner can still provision orgs from `/admin/tenants`. Self-signup never honours `DEMO_ACTIVATE_PLAN`; optional `activate_plan` on this create form still does.

## Plan override semantics (Sprint 32)

Three independent concepts — do not conflate them:

| Concept | Field / control | Effect |
| ------- | ---------------- | ------ |
| **Tenant suspended** | `tenants.status` · Suspend / Unsuspend on detail page | Hard block: agent, ingest, sync denied even when plan is active |
| **Plan inactive** | `billing_customers.plan_status=inactive` | No product entitlements until paid or waived |
| **Admin waiver** | `plan_source=admin` + `override_reason` · Activate plan (no Stripe) | Grants entitlements without Checkout; Stripe webhooks skip this row until Deactivate plan |
| **Stripe-managed** | `plan_source=stripe` | Checkout + Customer Portal + webhooks may change `plan_status` |

`PATCH /admin/tenants/{id}/plan` with `{ "plan_status": "active", "reason": "…" }` sets an admin waiver. `{ "plan_status": "inactive", "reason": "…" }` restores Stripe control (webhooks apply again).

Policy guardrail: `ALLOW_PLAN_WAIVERS` (see `.env.example`). When `false` (recommended in production), activating a waiver via API/UI returns 403; deactivating (restore Stripe) still works. Unset defaults to **allowed in `development`**, **denied in `staging`/`production`**.

Suspended tenants fail `plan_is_active` and Slack agent replies with a clear suspended message.

## Smoke

```bash
uv run alembic upgrade head
uv run python scripts/seed_demo.py
uv run pytest tests/admin -q

# Second org + knowledge isolation (Sprint 22.4)
uv run python scripts/second_org_smoke.py
uv run pytest tests/demo/test_second_org.py -q

# Web: sign in as owner@example.com → /admin/tenants (create form), /admin/health
```

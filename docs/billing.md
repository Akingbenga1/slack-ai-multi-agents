# Stripe billing

Org subscriptions via **Stripe Checkout** + **Customer Portal**. One Stripe Customer per tenant (`billing_customers`).

## Env

| Variable | Purpose |
| -------- | ------- |
| `STRIPE_SECRET_KEY` | Stripe secret (`sk_test_…`) |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret (Task 11.4) |
| `STRIPE_PRICE_ID` | Recurring Price id for Checkout (`price_…`) |
| `WEB_APP_URL` | Next.js origin for success/cancel / portal return (`http://localhost:3000`) |
| `PUBLIC_BASE_URL` | API public URL (webhook path later) |

Copy from `.env.example`. Without `STRIPE_SECRET_KEY`, `ensure_billing_customer` still creates a local `billing_customers` row (`plan_status=inactive`, no `stripe_customer_id`). Checkout/Portal fail closed until keys are set.

## Customers (Task 11.1)

- `ensure_billing_customer(db, tenant_id=…, email=…)` — idempotent create/retrieve; Stripe Customer metadata: `tenant_id`, `tenant_slug`, `client_id`.
- Demo seed (`scripts/seed_demo.py`) ensures a row for the demo tenant.
- `POST /billing/customers/ensure` — org_admin (or platform owner + `X-Client-Id`) ensures customer.
- `GET /billing/customers/me` — current tenant billing row.

## Checkout (Task 11.2)

- `POST /billing/checkout-session` → `{ "url": "https://checkout.stripe.com/…" }`
- Mode `subscription`, line item = `STRIPE_PRICE_ID`, customer = ensured Stripe customer.
- Success / cancel → `{WEB_APP_URL}/app/billing?checkout=success|cancel`
- Org portal page: `/app/billing`

## Customer Portal (Task 11.3)

- `POST /billing/portal-session` → `{ "url": "https://billing.stripe.com/…" }`
- Return URL → `{WEB_APP_URL}/app/billing`

## Webhooks (Task 11.4)

- `POST /billing/webhooks/stripe` — **no JWT**; verifies `Stripe-Signature` with `STRIPE_WEBHOOK_SECRET`.
- Handled events:
  - `checkout.session.completed` → `plan_status=active`, set `stripe_subscription_id`
  - `customer.subscription.updated` → active if Stripe status is `active`/`trialing`, else inactive
  - `customer.subscription.deleted` → inactive, clear subscription id
- Tenant resolution: Checkout `client_reference_id` / metadata → else `stripe_customer_id` / subscription id.
- Public URL: `{PUBLIC_BASE_URL}/billing/webhooks/stripe` (needs tunnel when not publicly reachable — see `docs/tunnel-plan.md`).

## Plan fields & entitlements (Task 11.5)

Per-tenant row on `billing_customers` (not duplicated on `tenants`):

| Field | Meaning |
| ----- | ------- |
| `plan_status` | `active` \| `inactive` |
| `stripe_subscription_id` | Current Stripe Subscription id (cleared on delete) |
| `entitlements` | JSON flags + budgets: `agent` / `ingest` / `sync` (bool); `tokens_daily` / `tokens_monthly` / `jobs_daily` (int when active) |

Helpers: `plan_is_active(db, tenant_id)`, `tenant_has_entitlement(db, tenant_id, "agent")`, `require_entitlement(...)`, `get_tenant_entitlements` in `api.app.billing.plans`. Rate limits / budgets / usage: `docs/governance.md`.

`GET /billing/customers/me` returns these fields; `/app/billing` shows status + entitlements.

### Local demo without Checkout

Set `DEMO_ACTIVATE_PLAN=true` then `uv run python scripts/seed_demo.py` to activate the demo tenant entitlements locally. See `docs/demo-readiness.md`.

## Needs human

1. Create a Stripe **test** mode account / product + recurring price.
2. Put `STRIPE_SECRET_KEY` and `STRIPE_PRICE_ID` in `.env`.
3. Configure webhook endpoint to `{PUBLIC_BASE_URL}/billing/webhooks/stripe` (events above) and set `STRIPE_WEBHOOK_SECRET` from the signing secret.
4. Live smoke: ensure customer → Checkout pay → webhook activates plan → Portal cancel → webhook deactivates.

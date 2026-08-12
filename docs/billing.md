# Billing (payment gateway)

Org subscriptions via a **payment provider** (Strategy). Demo default is the **Stripe** adapter: Checkout + Customer Portal. One external customer per tenant (`billing_customers`).

## Env

| Variable | Purpose |
| -------- | ------- |
| `PAYMENT_PROVIDER` | `stripe` (default) \| `paypal` (documented stub only — not implemented) |
| `STRIPE_SECRET_KEY` | Stripe-adapter secret (`sk_test_…`) |
| `STRIPE_WEBHOOK_SECRET` | Stripe-adapter webhook signing secret |
| `STRIPE_PRICE_ID` | Stripe-adapter recurring Price id for Checkout (`price_…`) |
| `WEB_APP_URL` | Next.js origin for success/cancel / portal return (`http://localhost:3000`) |
| `PUBLIC_BASE_URL` | API public URL (webhook path) |

Copy from `.env.example`. Without `STRIPE_SECRET_KEY` (when `PAYMENT_PROVIDER=stripe`), `ensure_billing_customer` still creates a local `billing_customers` row (`plan_status=inactive`, no `external_customer_id`). Checkout/Portal fail closed until keys are set.

Product code talks to `PaymentProvider` (`api.app.billing.provider`); Stripe SDK lives only in `StripePaymentProvider`.

## Customers

- `ensure_billing_customer(db, tenant_id=…, email=…)` — idempotent create/retrieve; gateway Customer metadata: `tenant_id`, `tenant_slug`, `client_id`.
- Demo seed (`scripts/seed_demo.py`) ensures a row for the demo tenant.
- `POST /billing/customers/ensure` — org_admin (or platform owner + `X-Client-Id`) ensures customer.
- `GET /billing/customers/me` — current tenant billing row (`provider`, `external_customer_id`, `external_subscription_id`, `plan_status`, `entitlements`).

## Checkout

- `POST /billing/checkout-session` → `{ "url": "…" }` (Stripe Checkout when adapter is Stripe)
- Mode `subscription`, line item = `STRIPE_PRICE_ID`, customer = ensured external customer.
- Success / cancel → `{WEB_APP_URL}/app/billing?checkout=success|cancel`
- Org portal page: `/app/billing`

## Customer Portal

- `POST /billing/portal-session` → `{ "url": "…" }`
- Return URL → `{WEB_APP_URL}/app/billing`

## Webhooks

- `POST /billing/webhooks/stripe` — **no JWT**; adapter-owned URL kept for Stripe Dashboard. Verifies `Stripe-Signature` with `STRIPE_WEBHOOK_SECRET`.
- Handled events:
  - `checkout.session.completed` → `plan_status=active`, set `external_subscription_id`
  - `customer.subscription.updated` → active if Stripe status is `active`/`trialing`, else inactive
  - `customer.subscription.deleted` → inactive, clear subscription id
- Tenant resolution: Checkout `client_reference_id` / metadata → else `external_customer_id` / subscription id.
- Public URL: `{PUBLIC_BASE_URL}/billing/webhooks/stripe` (needs tunnel when not publicly reachable — see `docs/tunnel-plan.md`).

## Plan fields & entitlements

Per-tenant row on `billing_customers` (not duplicated on `tenants`):

| Field | Meaning |
| ----- | ------- |
| `provider` | Payment adapter id (`stripe`, …) |
| `external_customer_id` | Gateway customer id |
| `external_subscription_id` | Gateway subscription id (cleared on delete) |
| `plan_status` | `active` \| `inactive` |
| `plan_source` | `admin` \| `stripe` — when `admin`, payment webhooks skip plan updates until operator deactivates waiver (`docs/admin-portal.md`) |
| `override_reason` | Operator note when `plan_source=admin` |
| `entitlements` | JSON flags + budgets: `agent` / `ingest` / `sync` (bool); `tokens_daily` / `tokens_monthly` / `jobs_daily` (int when active) |

Helpers: `plan_is_active(db, tenant_id)`, `tenant_has_entitlement(db, tenant_id, "agent")`, `require_entitlement(...)`, `get_tenant_entitlements` in `api.app.billing.plans`. Rate limits / budgets / usage: `docs/governance.md`.

`GET /billing/customers/me` returns these fields; `/app/billing` shows status + entitlements and talks **pay / manage subscription** (Stripe naming only in the adapter-secret footnote when `provider=stripe`).

### Local demo without Checkout

Set `DEMO_ACTIVATE_PLAN=true` then `uv run python scripts/seed_demo.py` to activate the demo tenant entitlements locally. See `docs/demo-readiness.md`.

Post-create waivers for any tenant: platform owner `PATCH /admin/tenants/{id}/plan` or `/admin/tenants/[id]` UI (Sprint 32). That path is separate from org self-serve Checkout on `/app/billing`.

## Needs human

1. Create a Stripe **test** mode account / product + recurring price.
2. Put `STRIPE_SECRET_KEY` and `STRIPE_PRICE_ID` in `.env` (`PAYMENT_PROVIDER=stripe`).
3. Configure webhook endpoint to `{PUBLIC_BASE_URL}/billing/webhooks/stripe` (events above) and set `STRIPE_WEBHOOK_SECRET` from the signing secret.
4. Live smoke: ensure customer → Checkout pay → webhook activates plan → Portal cancel → webhook deactivates.

# Task 32.1 — Admin plan override API

## Steps

- [x] Alembic migration — `billing_customers.plan_source`, `override_reason`
- [x] `PATCH /admin/tenants/{id}/plan` with `{ "plan_status", "reason" }`
- [x] Write `plan_status` / entitlements; audit as `tenant.plan.override`
- [x] Persist admin waiver (`plan_source=admin`) so Stripe webhooks skip locked rows
- [x] Create-time `activate_plan` and `DEMO_ACTIVATE_PLAN` set `plan_source=admin`
- [x] Tests — activate/deactivate + webhook skip when admin-locked

## Acceptance criteria

- [x] Owner can activate/deactivate plan on an existing tenant without Stripe
- [x] Override persisted on `billing_customers` with audit trail
- [x] Stripe webhooks do not overwrite `plan_source=admin` rows
- [x] No Strategy/Factory; no new env keys (ALLOW_PLAN_WAIVERS is Task 32.3)

# Task 32.3 — Semantics + guardrail

## Checklist

- [x] Document plan inactive vs tenant suspended vs Stripe-managed in `docs/admin-portal.md` and `docs/billing.md`
- [x] Webhook apply-plan honours `plan_source=admin` (Task 32.1 — verified via existing webhook tests)
- [x] Add `ALLOW_PLAN_WAIVERS` env + `Settings.plan_waivers_permitted()` (default allow in development)
- [x] Guardrail on activate waiver in `override_tenant_plan` + HTTP 403
- [x] Update `.env.example`

## Acceptance criteria

- [x] Semantics documented for operators
- [x] Webhook honour rule in place (32.1)
- [x] Policy guardrail env without renaming Stripe keys

# Task 32.2 — Admin UI control

## Checklist

- [x] Extend `/admin/tenants/[id]` detail types with `plan_source`, `override_reason`, Stripe ids
- [x] Show plan status vs tenant `suspended` vs Stripe-managed subscription distinctly
- [x] Add activate/deactivate plan control calling `PATCH /admin/tenants/{id}/plan` with required reason
- [x] Update `docs/admin-portal.md` for UI section
- [x] Light smoke (pytest admin tests still green)

## Acceptance criteria

- Control on `/admin/tenants/[id]` to activate/deactivate plan without Stripe
- Operators can distinguish plan inactive, tenant suspended, and Stripe-managed subscription (PO-01, PO-25)

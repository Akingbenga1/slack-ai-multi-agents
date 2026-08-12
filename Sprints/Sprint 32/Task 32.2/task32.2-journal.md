# Task 32.2 journal

## Status

completed

## Summary

Added plan override UI on `/admin/tenants/[id]`: a **Billing & access** section distinguishes tenant suspended vs plan entitlements vs admin waiver vs Stripe-managed billing; activate/deactivate controls call `PATCH /admin/tenants/{id}/plan` with a required audited reason.

## Acceptance criteria checklist

- [x] Control on detail page to activate/deactivate plan without Stripe
- [x] Operators can distinguish plan inactive, tenant suspended, and Stripe-managed subscription

## Decision log

- Kept suspend/unsuspend as separate **Tenant access actions**; plan override does not change `tenants.status`.
- Activate disabled only when plan is already active under admin waiver (stripe-active can be converted to waiver).

## Needs human

(none)

## Files changed

- `web/components/TenantDetailPanel.tsx`
- `docs/admin-portal.md` (route description; full semantics in 32.3)

## Resume notes

Continue **Task 32.3** — semantics + `ALLOW_PLAN_WAIVERS` guardrail.

## Open questions

(none)

## Smoke test results

Manual UI smoke deferred; API covered by existing `test_admin_plan_override`.

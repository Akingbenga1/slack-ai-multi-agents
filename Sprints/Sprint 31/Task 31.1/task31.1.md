# Task 31.1 — Public registration API

## Steps

- [x] Endpoint to create tenant, org admin user, membership, billing row, and default agent config (mirror `POST /admin/tenants`, scoped to self-signup)
- [x] Reject duplicate email; tenant isolation from the first row
- [x] Slack app install, Stripe keys, and tunnel remain operator concerns — signup must not require the owner to insert a tenant row
- [x] Do not require `DEMO_ACTIVATE_PLAN`; plan starts inactive (pay remains Sprint 19–20)
- [x] Light smoke: signup + duplicate-email + two orgs isolated

## Acceptance criteria

- [x] Public `POST /auth/signup` (no platform-owner JWT) provisions the same rows as admin create
- [x] Duplicate email / slug → 409
- [x] New org is a distinct `tenant_id` from demo / other signups
- [x] No new env keys; no Strategy/Factory

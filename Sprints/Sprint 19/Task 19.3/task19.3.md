# Task 19.3 — Tenant scoping hardening in UI

## Steps

- [x] `sessionTenantId` / `tenantMatchesSession` helpers — never trust URL tenant
- [x] Middleware strips foreign `?tenant_id=` / `?client_id=` / `?tenant=` for org_admin
- [x] `/app/t/[tenantId]` denies Org B when session is Org A
- [x] Portal pages + `apiAuthHeaders` use session tenant only; upload drops form `tenant_id`
- [x] Document in `docs/portal.md`

## Acceptance criteria

- [x] Org A cannot open Org B portal routes (OR-09)
- [x] Client widgets do not send a foreign `X-Client-Id` from the URL
- [x] API cross-tenant 403 still enforced (regression covered in config/uploads tests)

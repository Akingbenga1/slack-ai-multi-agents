# Task 19.3 journal

## Status

`completed`

## Summary

Hardened org portal tenant scoping: session-only tenant helpers, middleware query strip, `/app/t/{id}` deny UI for foreign tenants, shared `apiAuthHeaders`, upload no longer posts form `tenant_id`.

## Acceptance criteria checklist

- [x] Org B routes denied
- [x] No URL-derived foreign client id
- [x] API 403 regression covered

## Decision log

- Routes stay flat (`/app/...`); explicit `/app/t/[tenantId]` is the ACL check surface.
- Middleware redirects away spoof query params rather than 403 (keeps UX clean).

## Needs human

Optional: second seeded org + manual click of `/app/t/{other-uuid}`.

## Files changed

- `web/lib/tenant.ts`, `web/lib/api.ts`, `web/middleware.ts`
- `web/app/app/t/[tenantId]/page.tsx`
- Portal pages + Billing/Usage/Agent/Knowledge using `sessionTenantId`
- `docs/portal.md`
- `Sprints/Sprint 19/Task 19.3/*`

## Resume notes

Sprint 19 complete. Next: **Continue Sprint 20 from Task 20.1**.

## Commercial mapping

OR-09 — portal actions limited to own `client_id`.

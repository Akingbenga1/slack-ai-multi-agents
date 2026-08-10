# Task 3.4 journal

## Status

`completed`

## Summary

Seeded demo memberships via `scripts/seed_demo.py` / `ensure_demo_memberships`. Org admin → single demo tenant; platform owner → all-access, no membership rows. `/auth/membership` + `/invite` document the rule.

## Acceptance criteria checklist

- [x] Org admin one tenant — done
- [x] Platform owner all-access — done

## Decision log

- Stable UUIDs: tenant `11111111-…`, owner `22222222-…`, admin `33333333-…`.
- Full invite email/token flow deferred; page is documentation stub.

## Needs human

None.

## Files changed

- `api/app/membership.py`
- `scripts/seed_demo.py`
- `web/app/invite/page.tsx`
- `README.md`

## Resume notes

Sprint 3 exit met. Next: Sprint 4 Task 4.1.

## Open questions

None.

## Smoke test results

- `/auth/membership` admin → one `demo-org` tenant
- `/auth/membership` owner → `all_access: true`, empty tenants

# Task 21.1 — Tenant list + detail

## Steps

- [x] `require_platform_owner` + `GET /admin/tenants` + `GET /admin/tenants/{id}`
- [x] Aggregate plan status, Slack connected, last sync (`PO-01`, `PO-25`)
- [x] Next.js `/admin/tenants` list + `/admin/tenants/[id]` detail
- [x] Tests `tests/admin/test_admin_api.py` + `docs/admin-portal.md`

## Acceptance criteria

- [x] Platform owner can list all tenants without DB diving
- [x] Detail shows plan, Slack, sync freshness
- [x] Org admin receives 403 on admin APIs

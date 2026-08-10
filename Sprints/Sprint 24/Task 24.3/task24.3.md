# Task 24.3 — Colleague discover, copy, and modify

Stories: `TM-21` · Journey: `J11` · Isolation: `OR-09`, `PO-04a`

## Steps

- [x] List/search templates for tenant (API + agent intent)
- [x] **Copy** → personal/draft version; original unchanged
- [x] Edit personal draft (title / body text) without mutating shared original
- [x] Tenant isolation: Org A never sees Org B templates
- [x] Optional org portal list page (align Sprint 19–20 patterns)
- [x] Light tests for copy + isolation

## Acceptance criteria

- [x] Colleagues can list shared templates for their tenant only
- [x] Copy creates a personal draft owned by the copying user
- [x] Editing a copy does not change the shared original
- [x] Cross-tenant get/list/copy fails closed

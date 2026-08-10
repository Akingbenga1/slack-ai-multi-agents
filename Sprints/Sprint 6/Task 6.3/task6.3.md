# Task 6.3 — Upsert/search smoke

## Steps

- [x] Ensure collection + index (reuse 6.1 helpers)
- [x] Upsert one raw vector for tenant A and one for tenant B
- [x] Search as each tenant; prove no cross-tenant hits
- [x] Document smoke command in README / docs

## Acceptance criteria

- [x] Tenant A search returns only A’s point
- [x] Tenant B search returns only B’s point
- [x] Missing `client_id` still fail-closed

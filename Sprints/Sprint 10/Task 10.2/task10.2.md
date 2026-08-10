# Task 10.2 — Fail-closed tenant filter tests

## Steps

- [x] Automated test: tenant A query never returns tenant B points
- [x] Automated test: missing / empty `client_id` raises `TenantFilterRequired`
- [x] Assert every returned hit's payload `client_id` matches the query tenant
- [x] Prefer in-memory Qdrant (no Compose required for CI)

## Acceptance criteria

- [x] Test suite proves tenant A search cannot surface tenant B knowledge
- [x] Fail-closed missing `client_id` covered in automated tests

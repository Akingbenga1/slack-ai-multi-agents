# Task 30.2 — Web `apiClient` + optional load hook

## Steps

- [x] Add `apiClient.get/patch/post` wrapping `getApiBaseUrl` + `apiAuthHeaders` + JSON/`!ok` errors
- [x] Document admin vs org `X-Client-Id` usage (`null` omit vs session/target tenant)
- [x] Optional `useAuthenticatedResource` for load/error/busy
- [x] Migrate heaviest panels first (Agent, Usage, Workflows, Tenant admin, Billing)
- [x] Leave multipart upload on raw `fetch` (FormData)

## Acceptance criteria

- [x] Shared facade for JSON API calls (get/patch/post)
- [x] Heaviest panels no longer duplicate base URL + auth + `!ok` boilerplate
- [x] Admin calls omit `X-Client-Id` unless targeting a tenant; org calls use session tenant
- [x] No Strategy invented for UI widgets

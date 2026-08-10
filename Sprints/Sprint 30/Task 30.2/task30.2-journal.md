# Task 30.2 journal

## Status

completed

## Summary

Added portal Facade `apiClient` (`get`/`patch`/`post`) plus `orgClientHeaders` / `adminClientHeaders` and optional `useAuthenticatedResource`. Migrated the heaviest panels onto the client; multipart upload stays on raw `fetch`.

## Acceptance criteria checklist

- [x] Shared facade for JSON API calls (get/patch/post)
- [x] Heaviest panels no longer duplicate base URL + auth + `!ok` boilerplate
- [x] Admin calls omit `X-Client-Id` unless targeting a tenant; org calls use session tenant
- [x] No Strategy invented for UI widgets

## Decision log

- **Facade only** (`review.md` §5.9): no UI Strategy — interchangeable render algorithms do not exist.
- `clientId: null` for admin list/health/audit; target tenant id for admin tenant actions; session tenant for org panels.
- `UploadWidget` keeps FormData `fetch` (binary body / no JSON Content-Type).

## Needs human

(none new)

## Files changed

- `web/lib/api.ts`
- `web/lib/useAuthenticatedResource.ts` (new)
- `web/components/AgentSettingsPanel.tsx`
- `web/components/UsageSummaryPanel.tsx`
- `web/components/WorkflowsPanel.tsx`
- `web/components/TenantListPanel.tsx`
- `web/components/TenantDetailPanel.tsx`
- `web/components/BillingActions.tsx`
- `web/components/PlatformHealthPanel.tsx`
- `web/components/SyncStatusPanel.tsx`
- `web/components/IngestJobsPanel.tsx`
- `web/components/SlackConnectPanel.tsx`
- `web/components/PortalStatusBanners.tsx`

## Resume notes

Continue with Task 30.3 — docs update (`docs/agent.md` registry / Strategy / delivery + cross-links).

## Open questions

(none)

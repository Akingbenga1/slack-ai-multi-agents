# Task 20.4 journal

## Status

`completed`

## Summary

Added shared portal status banners (unpaid, Slack disconnected, latest sync failure) on `/app`, plus clearer sync empty/error callouts on Knowledge.

## Acceptance criteria checklist

- [x] Unpaid state
- [x] Disconnected Slack
- [x] Sync failures

## Decision log

- Home aggregates three common blockers; detail pages keep their own CTAs.
- Sync failure banner only when last failure is newer than (or equal to) last success.

## Needs human

None new (inherited Stripe / Slack live verify).

## Files changed

- `web/components/PortalStatusBanners.tsx`, `SyncStatusPanel.tsx`, `web/app/app/page.tsx`
- `docs/portal.md`
- `Sprints/Sprint 20/Task 20.4/*`

## Resume notes

Sprint 20 complete. Next: **Continue Sprint 21 from Task 21.1**.

## Commercial mapping

Org self-serve empty/error UX for pay, Slack, and sync.

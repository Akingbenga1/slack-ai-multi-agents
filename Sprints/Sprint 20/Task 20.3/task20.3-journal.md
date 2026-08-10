# Task 20.3 journal

## Status

`completed`

## Summary

Portal Slack connect: `GET /slack/connection`, OAuth callback redirects to `/app/slack`, and Connect/Reinstall CTA on the org portal.

## Acceptance criteria checklist

- [x] Start OAuth from portal
- [x] Show connection status
- [x] Cross-tenant denied
- [x] OR-08

## Decision log

- Callback always redirects to the Next.js portal (browser OAuth) instead of JSON.
- Install URL still uses `PUBLIC_BASE_URL` + session tenant id (state carries tenant).

## Needs human

Slack app credentials + tunnel + live install verify (`docs/slack-app-setup.md`).

## Files changed

- `api/app/slack/routes.py`
- `web/app/app/slack/page.tsx`, `web/components/SlackConnectPanel.tsx`, `OrgNav.tsx`, `web/app/app/page.tsx`
- `tests/slack/test_connection.py`
- `docs/slack-app-setup.md`, `docs/portal.md`
- `Sprints/Sprint 20/Task 20.3/*`

## Resume notes

Next in batch: **Task 20.4**.

## Smoke test results

```
uv run pytest tests/slack/test_connection.py -q
→ passed
```

## Commercial mapping

OR-08 — connect/install Slack from the portal.

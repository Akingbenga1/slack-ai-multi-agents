# Task 8.4 journal

## Status

`completed`

## Summary

Org portal `/app` now has a minimal knowledge upload widget. NextAuth sign-in mints a FastAPI Bearer JWT via `POST /auth/token` (same demo credentials) and stores it on the session. The client widget posts multipart `file` + `file_role` to `POST /uploads` and shows success JSON or an error.

## Acceptance criteria checklist

- [x] Org-auth upload via `/app` widget — done
- [x] Bearer + tenant-scoped API call — done (`Authorization` + optional `tenant_id`)
- [x] Success / failure visible — done
- [x] Portal polish deferred — done (Sprint 19)

## Decision log

- Keep Auth.js demo user table for shell login; attach API `accessToken` when FastAPI answers (login still works if API is down, but upload prompts re-login after API is up).
- No SessionProvider — server page passes token props into a client widget.
- Full knowledge/ingest status UI stays Sprint 19.

## Needs human

None for this task. Live “upload PDF → retrieve chunk” still needs Compose TEI/Qdrant + API + Celery worker + seeded demo users, then sign in as `admin@example.com` on `/app`.

## Files changed

- `web/lib/auth.ts`, `web/lib/api.ts`, `web/types/next-auth.d.ts`
- `web/components/UploadWidget.tsx`
- `web/app/app/page.tsx`
- `docs/uploads.md`, `README.md`
- `Sprints/Sprint 8/Task 8.4/*`, progress files

## Resume notes

Sprint 8 complete. Next: **Continue Sprint 9 from Task 9.1** (Slack conversations.list / history client).

## Open questions

None.

## Smoke test results

```
cd web && npm run build  →  success (/app includes UploadWidget)
API localhost:8000 not running this session — no live upload curl
```

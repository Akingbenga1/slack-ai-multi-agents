# Task 8.4 — Minimal org UI upload widget (Next.js)

## Steps

- [x] Bridge NextAuth session with FastAPI Bearer JWT (same demo credentials → `POST /auth/token`)
- [x] Org `/app` upload widget: file + `file_role`, call `POST /uploads`
- [x] Show success / failure response (no portal polish)
- [x] Light smoke (Next.js build)

## Acceptance criteria

- [x] Org-auth user on `/app` can upload a document (e.g. PDF) via the widget
- [x] Widget calls upload API with tenant-scoped Bearer auth
- [x] Success and failure states are visible in the UI
- [x] Full portal polish deferred (Sprint 19)

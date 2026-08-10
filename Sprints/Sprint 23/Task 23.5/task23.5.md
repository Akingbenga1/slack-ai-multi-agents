# Task 23.5 — Isolation, usage, and smoke tests

Stories: `TM-17`–`TM-19`, `TM-23` · Journey: `J10`

## Steps

- [x] Fail-closed `client_id` on download, store, PDF job, and rename
- [x] Record usage events (`file_job`, `pdf_generate`, `file_rename`)
- [x] Automated smoke: financial-report attach → PDF competitor analysis → rename
- [x] Document manual live smoke + Needs-human scopes

## Acceptance criteria

- [x] Cross-tenant path / blank `client_id` rejected in file-action helpers
- [x] Usage event types present for file job / PDF / rename
- [x] Offline J10 smoke passes without live Slack
- [x] Sprint 23 exit criteria met (or Needs-human only for live scopes)

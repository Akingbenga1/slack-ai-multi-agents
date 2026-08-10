# Task 8.2 — Upload API

## Steps

- [x] Settings + on-disk upload storage under `data/uploads/{client_id}/`
- [x] `file_role` enum: `document` | `slack_history` with allowed extensions
- [x] Multipart `POST /uploads` (auth + tenant scope)
- [x] Reject missing auth / cross-tenant / bad role or extension
- [x] Light API smoke tests

## Acceptance criteria

- [x] Authenticated org user can upload a file scoped to their tenant
- [x] `file_role=document` accepts PDF/DOCX/XLSX/CSV
- [x] `file_role=slack_history` accepts ZIP/JSON/NDJSON/CSV/XLSX
- [x] Unauthenticated or cross-tenant request rejected

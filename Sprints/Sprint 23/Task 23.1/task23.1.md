# Task 23.1 — Slack attachment / file reference intake

Stories: `TM-17` · Journey: `J10`

## Steps

- [x] Detect `files` on mention/DM events (and file permalink / `file_id` in text)
- [x] Download via Slack Web API with install-store bot token
- [x] Tenant-scope temp/upload storage under `data/uploads/{client_id}/`
- [x] Parse supported types via existing document parsers (PDF/DOCX/XLSX/CSV)
- [x] Wire into agent state as **attached evidence** (not only Qdrant RAG)
- [x] Add `files:read` to bot OAuth scopes; document reinstall need
- [x] Light unit tests for detect / parse / fail-closed `client_id`

## Acceptance criteria

- [x] Mention/DM with an attached supported file yields parsed text on agent state
- [x] Empty `client_id` cannot store or parse attachments
- [x] Unsupported / download failure surfaces a clear path (no cross-tenant leak)
- [x] Attached evidence alone is enough to avoid the hard RAG hedge when analysing the file

# Task 24.1 — Schema + storage for shared workflow templates

Stories: `TM-20` · Journey: `J11` · Label: `deferred:shared-workflow-library`

## Steps

- [x] Add `workflow_templates` model (tenant-scoped; versions / copy parent)
- [x] Alembic migration after `c3d8f12a9b20`
- [x] Persist original file under tenant upload root (`data/uploads/{client_id}/`)
- [x] Content-hash helper for idempotent re-store
- [x] Optional Qdrant ingest hook (`file_role=workflow` → document pipeline)
- [x] Light unit tests (fail-closed `client_id`, store + lookup)

## Acceptance criteria

- [x] Templates are keyed by `client_id` / `tenant_id` with title, Slack `file_id`, storage path, created_by
- [x] Bytes land under tenant upload root; path escape rejected
- [x] Optional ingest enqueue available without blocking store
- [x] Empty / foreign `client_id` cannot read or write templates

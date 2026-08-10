# Task 24.1 journal

## Status

`completed`

## Summary

Added `workflow_templates` schema + Alembic migration, tenant-scoped storage helpers (`store_upload` with `file_role=workflow`), content-hash idempotency, and optional Qdrant ingest enqueue for document-parseable types.

## Acceptance criteria checklist

- [x] Templates keyed by tenant with title / Slack file id / path / created_by
- [x] Bytes under tenant upload root
- [x] Optional ingest enqueue
- [x] Fail-closed empty / foreign client_id

## Decision log

- Single table with `visibility=shared|personal` and `parent_id` instead of a separate versions table (copies are personal rows)
- Postgres partial unique indexes for shared idempotency by hash and Slack file id
- `.md`/`.txt` allowed for store; ingest enqueue only for document-parseable extensions

## Needs human

- None new (migration applies with usual `uv run alembic upgrade head`)

## Files changed

- `api/app/db/models.py` — `WorkflowTemplate`
- `alembic/versions/d4e9a21b8c30_workflow_templates.py`
- `api/app/uploads/roles.py` — `FileRole.WORKFLOW`
- `api/app/ingest/upload_ingest.py` — workflow → document path
- `api/app/workflows/library.py`, `__init__.py`
- `tests/workflows/test_library.py`
- `docs/workflow-library.md`

## Resume notes

Task 24.2 wires Slack store intent on top of this library.

## Open questions

- None

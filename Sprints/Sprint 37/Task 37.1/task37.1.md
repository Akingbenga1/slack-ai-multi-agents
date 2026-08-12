# Task 37.1 — `BlobStore` + local adapter

**Source:** `Project-Documents/jira-task.md` · `review.md` architecture gap — blob / file-storage

## Steps

- [x] Define `BlobStore` Strategy: put / get / rename / resolve; mandatory `client_id` (fail-closed)
- [x] Treat stored relative paths (e.g. `workflow_templates.storage_relative_path`) as **blob keys**, not absolute filesystem paths
- [x] Implement `LocalDiskBlobStore` Adapter (`UPLOAD_DIR` / `data/uploads/{client_id}/`)
- [x] Factory `get_blob_store` via `BLOB_STORE` (`local` default; `s3` stub/extension)
- [x] Keep `UPLOAD_DIR` as the local-adapter root (no S3 bucket/credential env this sprint)
- [x] Update `.env.example`: `BLOB_STORE` selector; `UPLOAD_DIR` stays local secret
- [x] Light smoke: factory + fail-closed tenant key checks

## Acceptance criteria

- [x] Product file I/O can talk to a `BlobStore`; local disk is one adapter
- [x] put / get / rename / resolve are on the interface with mandatory `client_id`
- [x] `BLOB_STORE=local|s3` selects the adapter (s3 may raise not-implemented)

# Task 37.2 — Wire file call sites

**Source:** `Project-Documents/jira-task.md` · `review.md` architecture gap — blob / file-storage

## Steps

- [x] `store_upload` / portal uploads write via `BlobStore.put`
- [x] Slack attachment intake (+ raw fallback) uses `BlobStore`
- [x] Org-copy rename uses `BlobStore.rename` (blob keys, not `Path.rename`)
- [x] Workflow library store / load / copy uses `BlobStore.get` / `put`
- [x] Upload ingest loads bytes via `BlobStore.get` (parsers already accept bytes / buffers)
- [x] Call sites do not assume a local filesystem path (keys only)

## Acceptance criteria

- [x] Org copies, portal uploads, Slack intake, rename, workflow library store/load use `BlobStore`
- [x] Those modules do not assume a local filesystem path

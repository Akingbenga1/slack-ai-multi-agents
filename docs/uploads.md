# Knowledge uploads

Multipart API for org knowledge files (`file_role=document` or `slack_history`).

## Endpoint

`POST /uploads` (Bearer JWT required)

Form fields:

| Field | Required | Notes |
| ----- | -------- | ----- |
| `file` | yes | multipart file |
| `file_role` | yes | `document` \| `slack_history` |
| `tenant_id` | no | platform_owner may set; org_admin must match membership |

Tenant also from JWT membership or `X-Client-Id` (cross-tenant denied for org users).

### Allowed extensions

| `file_role` | Extensions |
| ----------- | ---------- |
| `document` | `.pdf` `.docx` `.xlsx` `.csv` |
| `slack_history` | `.zip` `.json` `.ndjson` `.csv` `.xlsx` |

Files are stored via ``BlobStore`` (`BLOB_STORE=local` demo default). The local adapter keeps blobs under `{UPLOAD_DIR}/{client_id}/{upload_id}_{filename}` (default `data/uploads/`). DB fields such as `relative_path` / `storage_relative_path` are **blob keys**, not absolute filesystem paths.

### Example

```bash
curl -sS -X POST "$API/uploads" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file_role=document" \
  -F "file=@./policy.pdf;type=application/pdf"
```

Response includes `upload_id`, `relative_path`, `status` (`queued` when ingest is enqueued; `stored` if `enqueue=false`), and `task_id` / `queue` when queued.

Optional form fields: `channel` (Slack history channel override), `enqueue` (default true).

## Settings

- `BLOB_STORE` (default `local`; `s3` stub/extension only) — see `.env.example`
- `UPLOAD_DIR` (default `data/uploads`) — local-adapter root

## Ingest job

Celery task `worker.ingest_upload` parses the stored file and upserts to Qdrant (tenant-scoped). Worker must be running:

```bash
uv run celery -A worker.celery_app worker --loglevel=INFO -Q high,default,low --pool=solo
```

### Status (Sprint 19.2)

| Method | Path | Purpose |
| ------ | ---- | ------- |
| `GET` | `/uploads/jobs?limit=20` | Recent `ingest_upload` jobs for the caller tenant |
| `GET` | `/uploads/status/{upload_id}` | Latest job for an upload id |

## Org UI

Next.js `/app/knowledge` (Sprint 19) — upload widget, ingest status table, Slack sync panel. See `docs/portal.md`.

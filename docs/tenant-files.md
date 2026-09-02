# Tenant file listing

Filesystem-backed inventory of all files stored under a tenant upload root (`{UPLOAD_DIR}/{client_id}/`).

Listing reads directly from disk — not from the database. Requires `BLOB_STORE=local` (returns **501** otherwise).

## Endpoint

`GET /tenant-files` (Bearer JWT required)

Tenant from JWT membership or `X-Client-Id`. Platform owners may list any tenant via `X-Client-Id`; org users are denied cross-tenant access.

### Query parameters

| Param | Notes |
| ----- | ----- |
| `prefix` | Optional subfolder filter under the tenant root |
| `limit` | Max entries (default 500, max 2000) |
| `cursor` | Pagination cursor — last `relative_path` from a truncated page |

### Response

```json
{
  "client_id": "<uuid>",
  "files": [
    {
      "relative_path": "workflows/template.txt",
      "filename": "template.txt",
      "size_bytes": 1234,
      "modified_at": "2026-03-30T12:00:00+00:00"
    }
  ],
  "truncated": false,
  "next_cursor": null
}
```

`relative_path` is tenant-root-relative (does not include the `client_id/` prefix).

### Example

```bash
curl -sS "$API/tenant-files?limit=100" \
  -H "Authorization: Bearer $TOKEN"
```

Platform owner listing another tenant:

```bash
curl -sS "$API/tenant-files" \
  -H "Authorization: Bearer $OWNER_TOKEN" \
  -H "X-Client-Id: $TENANT_ID"
```

## Download

`GET /tenant-files/content?key=<relative_path>` (Bearer JWT required)

Downloads one file by tenant-root-relative path (same `relative_path` values returned by the list endpoint).

Returns the file bytes with `Content-Disposition: attachment` so browsers save the file directly.

### Example

```bash
curl -sS -OJ "$API/tenant-files/content?key=workflows/template.txt" \
  -H "Authorization: Bearer $TOKEN"
```

## Portal download

Browser downloads use a same-origin proxy so the session cookie handles auth:

`GET /api/tenant-files/download?key=<relative_path>&filename=<name>&tenantId=<uuid>`

The UI renders each row as a **Download** link to that proxy, which streams the file from `GET /tenant-files/content`.

## Portal UI

| Portal | Page | Section |
| ------ | ---- | ------- |
| Org | `/app/knowledge` | Tenant files panel with per-row download |
| Admin | `/admin/tenants/[tenantId]` | Tenant files panel with per-row download |

## Out of scope

- DB merge with ingest jobs or workflow metadata
- Delete / rename from the UI

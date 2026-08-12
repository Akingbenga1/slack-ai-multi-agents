# Task 37.4 — Tests

**Source:** `Project-Documents/jira-task.md` · Sprint 37 exit

## Steps

- [x] Fail-closed `client_id` on store / load / rename (adapter + product helpers)
- [x] Source isolation: product file I/O / PDF export do not import `fpdf` or own filesystem blob I/O
- [x] Product upload / intake / rename / library / ingest talk `BlobStore`; PDF facade talks `PdfRenderer`
- [x] Existing upload + PDF / rename smokes still pass
- [x] Docs / `review.md` reflect Implemented blob + PDF gaps; demo default remains local disk + fpdf2
- [x] Sprint 37 exit: switching disk vs object store (or PDF library) is adapter + env — call sites not rewritten

## Acceptance criteria

- [x] Fail-closed `client_id` on store/load/rename
- [x] Existing upload + PDF/rename smokes still pass
- [x] Sprint 37 exit met: File I/O and PDF export do not import local paths or fpdf2 outside their adapters

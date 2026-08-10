# Task 8.1 — Parsers (PDF, DOCX, XLSX, CSV)

## Steps

- [x] Shared document extraction schema (text/table units + format)
- [x] PDF text extraction (per page)
- [x] DOCX text + table extraction
- [x] XLSX table extraction (sheets → row/table text units)
- [x] CSV table extraction (rows → text units)
- [x] Format dispatch helper by extension / MIME hint
- [x] Light fixture tests

## Acceptance criteria

- [x] PDF → non-empty text units with page locator
- [x] DOCX → paragraphs and/or tables as text units
- [x] XLSX / CSV → table rows (or sheet blocks) as text units
- [x] Empty / unreadable input → clear error or empty result (documented)

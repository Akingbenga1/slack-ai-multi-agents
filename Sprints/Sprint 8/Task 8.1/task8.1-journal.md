# Task 8.1 journal

## Status

`completed`

## Summary

Added non-Slack document extractors under `api/app/ingest/documents/`: PDF (per page), DOCX (paragraphs + tables), XLSX/CSV (row text units). Shared `DocumentUnit` / `ExtractedDocument` schema plus `extract_document` dispatch by extension, MIME, or explicit format. Separate from Sprint 7 Slack history parsers.

## Acceptance criteria checklist

- [x] PDF → page units — done
- [x] DOCX → paragraphs/tables — done
- [x] XLSX / CSV → row units — done
- [x] Empty / unsupported → `units=[]` or `UnsupportedDocumentFormatError` — done + docs

## Decision log

- Document units are distinct from `NormalizedMessage` (Slack schema stays Sprint 7).
- Tabular docs emit `header: value` row text (not Slack column mapping).
- Soft-empty extractions return zero units; unknown formats raise.

## Needs human

None.

## Files changed

- `api/app/ingest/documents/` (schema, pdf, docx, tabular, extract, `_io`)
- `api/app/ingest/__init__.py`
- `tests/ingest/documents/test_parsers.py`
- `docs/document-ingest.md`
- `Sprints/Sprint 8/` progress + task files

## Resume notes

Next: **Task 8.2 — Upload API** (multipart, `file_role`, auth + tenant scope).

## Open questions

None.

## Smoke test results

```
uv run pytest tests/ingest/documents -q  → 7 passed
uv run pytest tests/ingest -q            → 26 passed
```

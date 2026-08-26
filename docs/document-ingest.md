# Document ingest parsers

Non-Slack org uploads (`file_role=document`) are extracted into text/table units for later chunk → TEI → Qdrant (Tasks 8.2–8.3).

Slack history dumps (`file_role=slack_history`) keep using `api.app.ingest.parsers` (Sprint 7).

## Usage

```python
from api.app.ingest.documents import extract_document, DocumentFormat

doc = extract_document("policy.pdf")                 # format from extension
doc = extract_document(raw_bytes, filename="a.docx")
doc = extract_document(csv_text, format=DocumentFormat.CSV, filename="t.csv")

for unit in doc.units:
    print(unit.locator, unit.kind, unit.text[:80])
```

## Formats

| Format | Extractor | Units |
| ------ | --------- | ----- |
| PDF | `extract_pdf` | one unit per non-empty page (`page=N`) |
| DOCX | `extract_docx` | paragraphs + tables in body order |
| XLSX | `extract_xlsx` | one unit per non-empty row (`sheet=Name!row=N`); all sheets by default |
| CSV | `extract_csv` | one unit per non-empty row (`row=N`) as `header: value` |
| Markdown | `extract_markdown` | one unit per ATX heading section (`section=N`), else blank-line paragraphs |
| Plain text | `extract_txt` | one unit per blank-line paragraph (`paragraph=N`) |

Unsupported extension / MIME raises `UnsupportedDocumentFormatError`. A readable file with no extractable text returns `units=[]` (soft empty).

## Ingest (Task 8.3)

```python
from api.app.ingest import ingest_upload
from api.app.uploads import FileRole

result = ingest_upload(
    client_id="…-tenant-uuid-…",
    file_role=FileRole.DOCUMENT,
    relative_path="…/uuid_file.pdf",
    filename="file.pdf",
)
```

Celery: `worker.ingest_upload` (enqueued from `POST /uploads`). Point payloads use `kind=document` with deterministic uuid5 ids (`filename` + `locator` + chunk index).

## Tests

```bash
uv run pytest tests/ingest/documents tests/ingest/test_upload_ingest.py -q
```

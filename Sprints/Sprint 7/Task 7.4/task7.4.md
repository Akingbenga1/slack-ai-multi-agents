# Task 7.4 — CSV / Excel message dump parser

## Steps

- [x] Define column mapping (defaults + optional override) for history-role dumps
- [x] Parse CSV → yield normalized messages (`source_format=csv`)
- [x] Parse Excel (XLSX first sheet or named) → `source_format=xlsx`
- [x] Channel from column or explicit override; skip unusable rows
- [x] Light fixture tests

## Acceptance criteria

- [x] CSV with mapped columns → shared schema
- [x] XLSX with mapped columns → shared schema
- [x] Missing channel / ts / text → skip or clear error (documented)

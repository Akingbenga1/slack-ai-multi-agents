"""CSV / Excel document table extraction (not Slack history dumps)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pandas as pd

from api.app.ingest.documents._io import Readable, normalize_filename, read_bytes
from api.app.ingest.documents.schema import (
    DocumentFormat,
    DocumentUnit,
    DocumentUnitKind,
    ExtractedDocument,
)


def _cell_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value).strip()


def _row_to_text(headers: list[str], row: dict[str, Any]) -> str:
    parts: list[str] = []
    for h in headers:
        val = _cell_str(row.get(h))
        if not val:
            continue
        label = str(h).strip() or "col"
        parts.append(f"{label}: {val}")
    return " | ".join(parts)


def _dataframe_units(
    df: pd.DataFrame,
    *,
    source_format: DocumentFormat,
    filename: str | None,
    sheet_label: str | None = None,
    start_index: int = 0,
) -> list[DocumentUnit]:
    if df.empty:
        return []

    headers = [str(c) for c in df.columns.tolist()]
    units: list[DocumentUnit] = []
    records = df.to_dict(orient="records")

    for row_i, record in enumerate(records, start=1):
        text = _row_to_text(headers, record)
        if not text:
            continue
        if sheet_label:
            locator = f"sheet={sheet_label}!row={row_i}"
        else:
            locator = f"row={row_i}"
        units.append(
            DocumentUnit(
                text=text,
                unit_index=start_index + len(units),
                source_format=source_format,
                kind=DocumentUnitKind.TABLE_ROW,
                locator=locator,
                filename=filename,
            )
        )
    return units


def extract_csv(
    source: Readable | str,
    *,
    filename: str | None = None,
) -> ExtractedDocument:
    """
    Extract each non-empty CSV row as ``header: value`` text.

    Inline CSV strings (containing newlines) are supported for tests.
    """
    name = normalize_filename(filename)
    if isinstance(source, str) and "\n" not in source:
        path = Path(source)
        if path.is_file():
            name = name or normalize_filename(source)
            df = pd.read_csv(path)
        else:
            df = pd.read_csv(io.StringIO(source))
    elif isinstance(source, str):
        df = pd.read_csv(io.StringIO(source))
    else:
        raw = read_bytes(source)
        df = pd.read_csv(io.BytesIO(raw))
        if name is None and isinstance(source, (str, Path)):
            name = normalize_filename(str(source))

    units = _dataframe_units(df, source_format=DocumentFormat.CSV, filename=name)
    return ExtractedDocument(
        source_format=DocumentFormat.CSV,
        filename=name,
        units=units,
    )


def extract_xlsx(
    source: Readable,
    *,
    filename: str | None = None,
    sheet_name: str | int | None = None,
) -> ExtractedDocument:
    """
    Extract Excel rows as text units.

    By default reads **all** sheets. Pass ``sheet_name`` to limit to one sheet
    (name or 0-based index).
    """
    name = normalize_filename(filename)
    if name is None and isinstance(source, str):
        name = normalize_filename(source)

    raw = read_bytes(source)
    buf = io.BytesIO(raw)

    if sheet_name is not None:
        df = pd.read_excel(buf, sheet_name=sheet_name, engine="openpyxl")
        label = str(sheet_name) if not isinstance(sheet_name, int) else f"sheet{sheet_name}"
        # When index is used, prefer actual sheet name if available
        if isinstance(sheet_name, int):
            buf.seek(0)
            book = pd.ExcelFile(buf, engine="openpyxl")
            if 0 <= sheet_name < len(book.sheet_names):
                label = book.sheet_names[sheet_name]
        units = _dataframe_units(
            df,
            source_format=DocumentFormat.XLSX,
            filename=name,
            sheet_label=label,
        )
        return ExtractedDocument(
            source_format=DocumentFormat.XLSX,
            filename=name,
            units=units,
        )

    buf.seek(0)
    frames = pd.read_excel(buf, sheet_name=None, engine="openpyxl")
    units: list[DocumentUnit] = []
    for sheet, df in frames.items():
        sheet_units = _dataframe_units(
            df,
            source_format=DocumentFormat.XLSX,
            filename=name,
            sheet_label=str(sheet),
            start_index=len(units),
        )
        units.extend(sheet_units)

    return ExtractedDocument(
        source_format=DocumentFormat.XLSX,
        filename=name,
        units=units,
    )

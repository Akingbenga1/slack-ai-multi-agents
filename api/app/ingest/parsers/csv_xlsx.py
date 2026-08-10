"""Parse CSV / Excel Slack history dumps → NormalizedMessage."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, BinaryIO, Iterator, Mapping, TextIO, Union

import pandas as pd

from api.app.ingest.normalize import normalize_slack_message
from api.app.ingest.parsers.json_dump import MissingChannelError
from api.app.ingest.schema import NormalizedMessage, SourceFormat

PathLike = Union[str, Path]
CsvReadable = Union[PathLike, TextIO, BinaryIO, bytes, str]
XlsxReadable = Union[PathLike, BinaryIO, bytes]

# Logical field → accepted header aliases (case-insensitive, stripped)
_DEFAULT_ALIASES: dict[str, tuple[str, ...]] = {
    "channel": ("channel", "channel_id", "channelid", "channel name", "channel_name"),
    "ts": ("ts", "timestamp", "message_ts", "message timestamp", "time", "datetime"),
    "user": ("user", "user_id", "userid", "author", "sender"),
    "text": ("text", "message", "body", "content", "msg"),
    "thread_ts": ("thread_ts", "thread_timestamp", "parent_ts", "thread ts"),
}

# Required for a usable history row (channel may come from override)
_REQUIRED_FIELDS = ("ts", "text")


def default_column_map() -> dict[str, str]:
    """
    Return the first preferred header name per logical field.

    Callers may pass a partial override to ``column_map=`` (logical → actual header).
    """
    return {field: aliases[0] for field, aliases in _DEFAULT_ALIASES.items()}


def _normalize_header(name: object) -> str:
    return str(name).strip().lower().replace("-", "_")


def _resolve_columns(
    headers: list[str],
    column_map: Mapping[str, str] | None,
) -> dict[str, str]:
    """
    Map logical field → actual dataframe column name.

    Explicit ``column_map`` wins; otherwise match aliases case-insensitively.
    """
    by_norm = {_normalize_header(h): h for h in headers if h is not None and str(h).strip()}
    resolved: dict[str, str] = {}

    if column_map:
        for logical, header in column_map.items():
            key = str(logical).strip().lower()
            if key not in _DEFAULT_ALIASES:
                continue
            want = _normalize_header(header)
            if want in by_norm:
                resolved[key] = by_norm[want]
            else:
                # Exact header as given (pandas may keep original casing)
                for h in headers:
                    if str(h).strip() == str(header).strip():
                        resolved[key] = h
                        break

    for logical, aliases in _DEFAULT_ALIASES.items():
        if logical in resolved:
            continue
        for alias in aliases:
            norm = _normalize_header(alias)
            if norm in by_norm:
                resolved[logical] = by_norm[norm]
                break

    return resolved


def _cell_str(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    # Timestamps / datetimes → ISO-ish string usable as ts when Slack ts missing
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    text = str(value).strip()
    return text or None


def _row_to_raw(
    row: Mapping[str, Any],
    columns: Mapping[str, str],
    *,
    channel_override: str | None,
) -> dict[str, Any]:
    raw: dict[str, Any] = {"type": "message"}
    for logical, col in columns.items():
        if col not in row:
            continue
        val = _cell_str(row[col])
        if val is not None:
            raw[logical] = val
    if channel_override and "channel" not in raw:
        raw["channel"] = channel_override
    return raw


def _iter_dataframe(
    df: pd.DataFrame,
    *,
    channel: str | None,
    column_map: Mapping[str, str] | None,
    source_format: SourceFormat,
) -> Iterator[NormalizedMessage]:
    if df.empty:
        return

    headers = [str(c) for c in df.columns.tolist()]
    columns = _resolve_columns(headers, column_map)

    missing_required = [f for f in _REQUIRED_FIELDS if f not in columns]
    if missing_required:
        raise ValueError(
            "CSV/Excel dump missing required columns "
            f"{missing_required}; provide column_map= or rename headers "
            f"(aliases: {_DEFAULT_ALIASES})"
        )

    has_channel_col = "channel" in columns
    if not has_channel_col and not channel:
        raise MissingChannelError(
            "tabular dump has no channel column; pass channel= override or "
            "include a channel / channel_id column"
        )

    records = df.to_dict(orient="records")
    for record in records:
        raw = _row_to_raw(record, columns, channel_override=channel)
        msg = normalize_slack_message(
            raw,
            channel=channel,
            source_format=source_format,
        )
        if msg is not None:
            yield msg


def _read_csv_frame(source: CsvReadable) -> pd.DataFrame:
    if isinstance(source, Path):
        return pd.read_csv(source)
    if isinstance(source, str):
        path = Path(source)
        if "\n" not in source and path.is_file():
            return pd.read_csv(path)
        return pd.read_csv(io.StringIO(source))
    if isinstance(source, (bytes, bytearray)):
        return pd.read_csv(io.BytesIO(bytes(source)))
    # file-like
    return pd.read_csv(source)


def _read_xlsx_frame(
    source: XlsxReadable,
    *,
    sheet_name: str | int = 0,
) -> pd.DataFrame:
    if isinstance(source, Path):
        return pd.read_excel(source, sheet_name=sheet_name, engine="openpyxl")
    if isinstance(source, str):
        return pd.read_excel(Path(source), sheet_name=sheet_name, engine="openpyxl")
    if isinstance(source, (bytes, bytearray)):
        return pd.read_excel(
            io.BytesIO(bytes(source)),
            sheet_name=sheet_name,
            engine="openpyxl",
        )
    return pd.read_excel(source, sheet_name=sheet_name, engine="openpyxl")


def iter_csv_messages(
    source: CsvReadable,
    *,
    channel: str | None = None,
    column_map: Mapping[str, str] | None = None,
    source_format: SourceFormat = SourceFormat.CSV,
) -> Iterator[NormalizedMessage]:
    """
    Parse a CSV history dump.

    Default headers (any alias): channel, ts, user, text, thread_ts.
    Pass ``column_map`` as logical field → actual header when names differ.
    """
    df = _read_csv_frame(source)
    yield from _iter_dataframe(
        df,
        channel=channel,
        column_map=column_map,
        source_format=source_format,
    )


def iter_xlsx_messages(
    source: XlsxReadable,
    *,
    channel: str | None = None,
    column_map: Mapping[str, str] | None = None,
    sheet_name: str | int = 0,
    source_format: SourceFormat = SourceFormat.XLSX,
) -> Iterator[NormalizedMessage]:
    """
    Parse an Excel (.xlsx) history dump (first sheet by default).

    Same column mapping rules as ``iter_csv_messages``.
    """
    df = _read_xlsx_frame(source, sheet_name=sheet_name)
    yield from _iter_dataframe(
        df,
        channel=channel,
        column_map=column_map,
        source_format=source_format,
    )

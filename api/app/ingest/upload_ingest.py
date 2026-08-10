"""Ingest a stored upload (document or slack_history) into Qdrant."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from api.app.ingest.document_pipeline import DocumentIngestResult, ingest_extracted_document
from api.app.ingest.documents import extract_document
from api.app.ingest.parsers import (
    iter_csv_messages,
    iter_json_messages,
    iter_ndjson_messages,
    iter_slack_export_zip,
    iter_xlsx_messages,
)
from api.app.ingest.pipeline import IngestResult, ingest_messages
from api.app.settings import Settings, get_settings
from api.app.uploads.roles import FileRole
from api.app.uploads.storage import resolve_stored_path


@dataclass
class UploadIngestResult:
    client_id: str
    file_role: FileRole
    filename: str
    unit_or_message_count: int
    chunk_count: int
    point_ids: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "file_role": str(self.file_role),
            "filename": self.filename,
            "unit_or_message_count": self.unit_or_message_count,
            "chunk_count": self.chunk_count,
            "point_count": len(self.point_ids),
            "point_ids": self.point_ids[:50],  # cap for job result size
        }


def _slack_format_from_filename(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    mapping = {
        ".zip": "zip",
        ".json": "json",
        ".ndjson": "ndjson",
        ".csv": "csv",
        ".xlsx": "xlsx",
    }
    if ext not in mapping:
        raise ValueError(f"Unsupported slack_history extension: {ext}")
    return mapping[ext]


def _load_slack_messages(path: Path, filename: str, channel: str | None):
    fmt = _slack_format_from_filename(filename)
    if fmt == "zip":
        return list(iter_slack_export_zip(path))
    if fmt == "json":
        return list(iter_json_messages(path, channel=channel))
    if fmt == "ndjson":
        return list(iter_ndjson_messages(path, channel=channel))
    if fmt == "csv":
        return list(iter_csv_messages(path, channel=channel))
    if fmt == "xlsx":
        return list(iter_xlsx_messages(path, channel=channel))
    raise ValueError(f"unsupported slack_history format: {fmt}")


def ingest_upload(
    *,
    client_id: str,
    file_role: FileRole | str,
    relative_path: str,
    filename: str,
    channel: Optional[str] = None,
    settings: Settings | None = None,
) -> UploadIngestResult:
    """
    Parse a stored upload and upsert vectors for ``client_id``.

    ``relative_path`` is relative to ``settings.upload_dir``.
    """
    settings = settings or get_settings()
    role = file_role if isinstance(file_role, FileRole) else FileRole(str(file_role))
    path = resolve_stored_path(settings.upload_dir_path, relative_path)
    if not path.is_file():
        raise FileNotFoundError(f"upload not found: {relative_path}")

    if role is FileRole.DOCUMENT or role is FileRole.WORKFLOW:
        doc = extract_document(path, filename=filename)
        result: DocumentIngestResult = ingest_extracted_document(
            client_id=client_id,
            document=doc,
            settings=settings,
        )
        return UploadIngestResult(
            client_id=client_id,
            file_role=role,
            filename=filename,
            unit_or_message_count=result.unit_count,
            chunk_count=result.chunk_count,
            point_ids=result.point_ids,
        )

    if role is FileRole.SLACK_HISTORY:
        messages = _load_slack_messages(path, filename, channel)
        result_m: IngestResult = ingest_messages(
            client_id=client_id,
            messages=messages,
            settings=settings,
        )
        return UploadIngestResult(
            client_id=client_id,
            file_role=role,
            filename=filename,
            unit_or_message_count=result_m.message_count,
            chunk_count=result_m.chunk_count,
            point_ids=result_m.point_ids,
        )

    raise ValueError(f"Unknown file_role: {role}")

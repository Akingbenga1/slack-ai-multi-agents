"""Shared Slack message fields for all bootstrap + live sync formats."""

from __future__ import annotations

from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SourceFormat(StrEnum):
    """Where a message came from (bootstrap dump or live sync)."""

    SLACK_EXPORT = "slack_export"
    JSON = "json"
    NDJSON = "ndjson"
    CSV = "csv"
    XLSX = "xlsx"
    WEB_API = "web_api"


class NormalizedMessage(BaseModel):
    """Canonical message used by parsers → chunk → embed → upsert."""

    channel: str = Field(..., min_length=1, description="Slack channel id or export name")
    ts: str = Field(..., min_length=1, description="Slack message timestamp id")
    user: Optional[str] = Field(None, description="Slack user id when present")
    text: str = Field(..., min_length=1, description="Message body (non-empty)")
    thread_ts: Optional[str] = Field(None, description="Parent thread ts when a reply")
    source_format: SourceFormat

    @field_validator("channel", "ts", "text", mode="before")
    @classmethod
    def _strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("user", "thread_ts", mode="before")
    @classmethod
    def _strip_optional(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @property
    def content_key(self) -> str:
        """Stable id for idempotent upsert (channel + ts)."""
        return f"{self.channel}:{self.ts}"

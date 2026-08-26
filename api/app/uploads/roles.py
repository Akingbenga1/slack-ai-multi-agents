"""Knowledge file uploads (documents + Slack history dumps)."""

from __future__ import annotations

from enum import StrEnum


class FileRole(StrEnum):
    """Upload intent — selects parser path on ingest."""

    DOCUMENT = "document"
    SLACK_HISTORY = "slack_history"
    # Shared workflow library files (Sprint 24) — same parsers as documents
    WORKFLOW = "workflow"


# Extensions allowed per role (lowercase, with dot)
DOCUMENT_EXTENSIONS: frozenset[str] = frozenset(
    {".pdf", ".docx", ".xlsx", ".csv", ".md", ".txt"}
)
SLACK_HISTORY_EXTENSIONS: frozenset[str] = frozenset(
    {".zip", ".json", ".ndjson", ".csv", ".xlsx"}
)
WORKFLOW_EXTENSIONS: frozenset[str] = frozenset(
    {".pdf", ".docx", ".xlsx", ".csv", ".md", ".txt", ".markdown", ".text"}
)


def allowed_extensions(role: FileRole) -> frozenset[str]:
    if role is FileRole.DOCUMENT:
        return DOCUMENT_EXTENSIONS
    if role is FileRole.SLACK_HISTORY:
        return SLACK_HISTORY_EXTENSIONS
    if role is FileRole.WORKFLOW:
        return WORKFLOW_EXTENSIONS
    raise ValueError(f"Unknown file_role: {role}")

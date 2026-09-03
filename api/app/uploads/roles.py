"""Knowledge file uploads (documents + Slack history dumps)."""

from __future__ import annotations

from enum import StrEnum


class FileRole(StrEnum):
    """Upload intent — selects the parser path on ingest, or opts out of it."""

    DOCUMENT = "document"
    SLACK_HISTORY = "slack_history"
    # Shared workflow library files (Sprint 24) — same parsers as documents
    WORKFLOW = "workflow"
    # Opaque payload handed to the agent executor. Never parsed or ingested,
    # so no parser-driven extension policy applies.
    AGENT_ATTACHMENT = "agent_attachment"


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


def allowed_extensions(role: FileRole) -> frozenset[str] | None:
    """Extensions permitted for ``role``; ``None`` means unrestricted.

    A role restricts extensions only because its bytes are routed to a parser
    on ingest. Roles whose bytes are never parsed carry no extension policy,
    so they accept any payload the caller supplies.
    """
    if role is FileRole.DOCUMENT:
        return DOCUMENT_EXTENSIONS
    if role is FileRole.SLACK_HISTORY:
        return SLACK_HISTORY_EXTENSIONS
    if role is FileRole.WORKFLOW:
        return WORKFLOW_EXTENSIONS
    if role is FileRole.AGENT_ATTACHMENT:
        return None
    raise ValueError(f"Unknown file_role: {role}")

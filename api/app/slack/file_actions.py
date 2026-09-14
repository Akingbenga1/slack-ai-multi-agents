"""Slack file deliverables (rename).

Implementation lives in ``api.app.slack.files``. This module re-exports the
public surface for existing imports (for example MCP tools).
"""

from api.app.slack.files import (
    MSG_FILE_JOB_DENIED,
    MSG_RENAME_FAILED,
    MSG_RENAME_NO_TARGET,
    MSG_RENAME_OK,
    MSG_RENAME_PARTIAL,
    parse_requested_filename,
    rename_slack_file_or_copy,
    rename_stored_org_copy,
)

__all__ = [
    "MSG_FILE_JOB_DENIED",
    "MSG_RENAME_FAILED",
    "MSG_RENAME_NO_TARGET",
    "MSG_RENAME_OK",
    "MSG_RENAME_PARTIAL",
    "parse_requested_filename",
    "rename_slack_file_or_copy",
    "rename_stored_org_copy",
]

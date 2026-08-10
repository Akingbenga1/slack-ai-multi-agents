"""Slack files facade — refs / intake / pdf / rename (Sprint 26.3).

Delivery strategies and callers import from here (or from legacy
``attachments`` / ``file_actions`` shims).
"""

from api.app.slack.files.intake import IntakeResult, intake_attachments
from api.app.slack.files.pdf import (
    MSG_PDF_NO_ATTACHMENT,
    MSG_PDF_OK,
    MSG_PDF_UPLOAD_FAILED,
    produce_and_upload_analysis_pdf,
)
from api.app.slack.files.refs import (
    AttachedEvidence,
    SlackFileRef,
    evidence_has_usable_text,
    evidence_to_chunks,
    files_from_event,
    first_usable_evidence,
    require_client_id,
)
from api.app.slack.files.rename import (
    MSG_FILE_JOB_DENIED,
    MSG_RENAME_FAILED,
    MSG_RENAME_NO_TARGET,
    MSG_RENAME_OK,
    MSG_RENAME_PARTIAL,
    parse_requested_filename,
    question_requests_rename,
    rename_slack_file_or_copy,
    rename_stored_org_copy,
)

__all__ = [
    "AttachedEvidence",
    "IntakeResult",
    "MSG_FILE_JOB_DENIED",
    "MSG_PDF_NO_ATTACHMENT",
    "MSG_PDF_OK",
    "MSG_PDF_UPLOAD_FAILED",
    "MSG_RENAME_FAILED",
    "MSG_RENAME_NO_TARGET",
    "MSG_RENAME_OK",
    "MSG_RENAME_PARTIAL",
    "SlackFileRef",
    "evidence_has_usable_text",
    "evidence_to_chunks",
    "files_from_event",
    "first_usable_evidence",
    "intake_attachments",
    "parse_requested_filename",
    "produce_and_upload_analysis_pdf",
    "question_requests_rename",
    "rename_slack_file_or_copy",
    "rename_stored_org_copy",
    "require_client_id",
]

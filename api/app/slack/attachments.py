"""Slack attachment / file-reference intake (Sprint 23.1).

Implementation lives in ``api.app.slack.files`` (Sprint 26.3). This module
re-exports the public surface for existing imports.
"""

from api.app.slack.files import (
    AttachedEvidence,
    IntakeResult,
    SlackFileRef,
    evidence_has_usable_text,
    evidence_to_chunks,
    files_from_event,
    intake_attachments,
    require_client_id,
)

__all__ = [
    "AttachedEvidence",
    "IntakeResult",
    "SlackFileRef",
    "evidence_has_usable_text",
    "evidence_to_chunks",
    "files_from_event",
    "intake_attachments",
    "require_client_id",
]

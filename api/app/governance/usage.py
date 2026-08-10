"""Usage event recording (Sprint 12.3)."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.db.models import UsageEvent
from api.app.logging_config import get_logger

logger = get_logger("api.governance.usage")

# Canonical event_type values
EVENT_SLACK_MENTION = "slack_mention"
EVENT_LLM_TOKENS = "llm_tokens"
EVENT_SYNC_RUN = "sync_run"
EVENT_JOB = "job"
EVENT_REPORT_POST = "report_post"
EVENT_INGEST = "ingest"
EVENT_FILE_JOB = "file_job"
EVENT_PDF_GENERATE = "pdf_generate"
EVENT_FILE_RENAME = "file_rename"
EVENT_WORKFLOW_STORE = "workflow_store"
EVENT_WORKFLOW_COPY = "workflow_copy"

# Events that count toward the jobs_daily budget
JOB_BUDGET_EVENT_TYPES = frozenset(
    {
        EVENT_SYNC_RUN,
        EVENT_JOB,
        EVENT_INGEST,
        EVENT_REPORT_POST,
        EVENT_FILE_JOB,
        EVENT_PDF_GENERATE,
        EVENT_FILE_RENAME,
        EVENT_WORKFLOW_STORE,
        EVENT_WORKFLOW_COPY,
    }
)

# Events that count toward token budgets
TOKEN_BUDGET_EVENT_TYPES = frozenset({EVENT_LLM_TOKENS})


def record_usage(
    db: Session,
    tenant_id: UUID | str,
    event_type: str,
    *,
    units: int = 1,
    meta: Optional[dict[str, Any]] = None,
    commit: bool = False,
) -> UsageEvent:
    """
    Persist a `usage_events` row for the tenant.

    Caller owns the transaction unless `commit=True`.
    """
    tid = UUID(str(tenant_id))
    units_i = max(0, int(units))
    row = UsageEvent(
        tenant_id=tid,
        event_type=event_type,
        units=units_i,
        meta=meta,
    )
    db.add(row)
    db.flush()
    if commit:
        db.commit()
        db.refresh(row)
    logger.info(
        "usage_recorded tenant_id=%s event_type=%s units=%s",
        tid,
        event_type,
        units_i,
    )
    return row

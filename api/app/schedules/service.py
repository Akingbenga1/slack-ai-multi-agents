"""Schedule read/write helpers on store + kind Strategies (Sprint 28)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.db.models import AgentConfig
from api.app.schedules.kinds import (
    RECURRING_REPORT_KEY,
    SLACK_HISTORY_SYNC_KEY,
    get_schedule_kind,
    list_due_for_kind,
    list_due_recurring_reports,
)
from api.app.schedules.store import get_block, upsert_block


def read_kind(db: Session, tenant_id: UUID, key: str) -> dict[str, Any]:
    strategy = get_schedule_kind(key)
    return strategy.normalize(get_block(db, tenant_id, key))


def patch_kind(
    db: Session,
    *,
    tenant_id: UUID,
    key: str,
    patch: dict[str, Any],
    commit: bool = True,
) -> AgentConfig:
    strategy = get_schedule_kind(key)
    current = get_block(db, tenant_id, key)
    block = strategy.apply_patch(current, patch)
    return upsert_block(
        db,
        tenant_id=tenant_id,
        key=key,
        block=block,
        merge=False,
        commit=commit,
    )


def read_all_kinds(db: Session, tenant_id: UUID) -> dict[str, Any]:
    return {
        SLACK_HISTORY_SYNC_KEY: read_kind(db, tenant_id, SLACK_HISTORY_SYNC_KEY),
        RECURRING_REPORT_KEY: read_kind(db, tenant_id, RECURRING_REPORT_KEY),
    }


def patch_schedules(
    db: Session,
    *,
    tenant_id: UUID,
    slack_history_sync: dict[str, Any] | None = None,
    recurring_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Apply one or both kind patches in a single transaction.

    Returns normalized schedule map for both keys.
    """
    if slack_history_sync is None and recurring_report is None:
        raise ValueError("at least one schedule kind patch required")
    if slack_history_sync is not None:
        patch_kind(
            db,
            tenant_id=tenant_id,
            key=SLACK_HISTORY_SYNC_KEY,
            patch=slack_history_sync,
            commit=False,
        )
    if recurring_report is not None:
        patch_kind(
            db,
            tenant_id=tenant_id,
            key=RECURRING_REPORT_KEY,
            patch=recurring_report,
            commit=False,
        )
    db.commit()
    return read_all_kinds(db, tenant_id)


__all__ = [
    "list_due_for_kind",
    "list_due_recurring_reports",
    "patch_kind",
    "patch_schedules",
    "read_all_kinds",
    "read_kind",
]

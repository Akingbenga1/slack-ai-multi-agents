"""Per-tenant Slack history sync schedule (enable/disable for Beat).

Persistence: ``ScheduleStore``. Kind rules: ``SlackHistorySyncStrategy``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from api.app.db.models import AgentConfig
from api.app.schedules.kinds import SLACK_HISTORY_SYNC_KEY, list_due_for_kind
from api.app.schedules.service import patch_kind, read_kind
from api.app.schedules.store import DEFAULT_AGENT_NAME

SCHEDULE_KEY = SLACK_HISTORY_SYNC_KEY
# Beat only: missing / unset schedules → enabled (default hourly).
DEFAULT_SYNC_ENABLED = True


def is_slack_history_sync_enabled(db: Session, tenant_id: UUID) -> bool:
    """Return whether periodic Beat should enqueue sync for this tenant."""
    return bool(read_kind(db, tenant_id, SCHEDULE_KEY)["enabled"])


def set_slack_history_sync_enabled(
    db: Session,
    *,
    tenant_id: UUID,
    enabled: bool,
) -> AgentConfig:
    """Upsert default agent_config schedules.slack_history_sync.enabled."""
    return patch_kind(
        db,
        tenant_id=tenant_id,
        key=SCHEDULE_KEY,
        patch={"enabled": enabled},
    )


def list_tenants_for_scheduled_slack_sync(db: Session) -> list[UUID]:
    """
    Tenants that should receive the hourly Beat enqueue.

    Requires a Slack install, active ``sync`` entitlement, and sync not
    explicitly disabled.
    """
    return list_due_for_kind(db, SCHEDULE_KEY)


__all__ = [
    "DEFAULT_AGENT_NAME",
    "DEFAULT_SYNC_ENABLED",
    "SCHEDULE_KEY",
    "is_slack_history_sync_enabled",
    "list_tenants_for_scheduled_slack_sync",
    "set_slack_history_sync_enabled",
]

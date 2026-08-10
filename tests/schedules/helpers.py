"""Shared schedule fixtures after ScheduleStore + kind Strategy unification (28.4).

Smell: twin FakeDB / in-memory schedule stores in slack vs reports tests.
One block factory + FakeScheduleDB + MemorySchedules backs unit, jobs API, and
agent schedules tests.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID

from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList, Grouping

from api.app.db.models import AgentConfig
from api.app.schedules.kinds import (
    RECURRING_REPORT_KEY,
    SLACK_HISTORY_SYNC_KEY,
    get_schedule_kind,
    window_label_for_cadence,
)
from api.app.schedules.store import DEFAULT_AGENT_NAME


def sync_block(*, enabled: bool = True) -> dict[str, Any]:
    """Canonical ``slack_history_sync`` JSONB block."""
    return {"enabled": bool(enabled)}


def report_block(
    *,
    enabled: bool = False,
    channel_id: str | None = None,
    cadence: str = "weekly",
    window_label: str | None = None,
) -> dict[str, Any]:
    """Canonical ``recurring_report`` JSONB block."""
    return {
        "enabled": bool(enabled),
        "channel_id": channel_id,
        "cadence": cadence,
        "window_label": window_label or window_label_for_cadence(cadence),
    }


def _clause_eq_value(clause: Any, column_key: str) -> Any | None:
    if isinstance(clause, BooleanClauseList):
        for child in clause.clauses:
            found = _clause_eq_value(child, column_key)
            if found is not None:
                return found
        return None
    if isinstance(clause, Grouping):
        return _clause_eq_value(clause.element, column_key)
    if isinstance(clause, BinaryExpression):
        left, right = clause.left, clause.right
        if getattr(left, "key", None) == column_key:
            return getattr(right, "value", right)
        if getattr(right, "key", None) == column_key:
            return getattr(left, "value", left)
    return None


def _tenant_id_from_stmt(stmt: Any) -> UUID | None:
    wheres = getattr(stmt, "_where_criteria", ()) or ()
    for crit in wheres:
        value = _clause_eq_value(crit, "tenant_id")
        if value is not None:
            return value if isinstance(value, UUID) else UUID(str(value))
    whereclause = getattr(stmt, "whereclause", None)
    if whereclause is not None:
        value = _clause_eq_value(whereclause, "tenant_id")
        if value is not None:
            return value if isinstance(value, UUID) else UUID(str(value))
    return None


class FakeScheduleDB:
    """
    Minimal Session stand-in for ``ScheduleStore`` AgentConfig CRUD + install listing.

    ``scalar`` resolves ``AgentConfig`` by ``tenant_id`` in the SELECT WHERE clause.
    ``scalars`` returns Slack-install candidate tenant ids for Beat due-lists.
    """

    def __init__(
        self,
        *,
        configs: dict[UUID, AgentConfig] | None = None,
        install_tenant_ids: list[UUID] | None = None,
    ):
        self.configs: dict[UUID, AgentConfig] = dict(configs or {})
        self.install_tenant_ids: list[UUID] = list(install_tenant_ids or [])

    def seed(
        self,
        tenant_id: UUID,
        schedules: dict[str, dict[str, Any]] | None = None,
    ) -> AgentConfig:
        cfg = AgentConfig(
            tenant_id=tenant_id,
            name=DEFAULT_AGENT_NAME,
            schedules=dict(schedules or {}),
        )
        self.configs[tenant_id] = cfg
        return cfg

    def scalar(self, stmt: Any) -> AgentConfig | None:
        tenant_id = _tenant_id_from_stmt(stmt)
        if tenant_id is not None:
            return self.configs.get(tenant_id)
        if len(self.configs) == 1:
            return next(iter(self.configs.values()))
        return None

    def scalars(self, _stmt: Any) -> SimpleNamespace:
        return SimpleNamespace(all=lambda: list(self.install_tenant_ids))

    def add(self, row: Any) -> None:
        if isinstance(row, AgentConfig):
            self.configs[row.tenant_id] = row

    def commit(self) -> None:
        return None

    def refresh(self, row: Any) -> Any:
        return row

    def close(self) -> None:
        return None


class MemorySchedules:
    """
    In-memory schedule blocks for HTTP tests that patch jobs/agent facades.

    Uses kind Strategies for normalize / apply_patch so API fakes stay aligned
    with production validation.
    """

    def __init__(self) -> None:
        self.blocks: dict[UUID, dict[str, dict[str, Any]]] = {}

    def _raw(self, tenant_id: UUID, key: str) -> dict[str, Any] | None:
        return self.blocks.get(tenant_id, {}).get(key)

    def _put(self, tenant_id: UUID, key: str, block: dict[str, Any]) -> None:
        self.blocks.setdefault(tenant_id, {})[key] = dict(block)

    def is_slack_history_sync_enabled(self, _db: Any, tenant_id: UUID) -> bool:
        strategy = get_schedule_kind(SLACK_HISTORY_SYNC_KEY)
        return bool(strategy.normalize(self._raw(tenant_id, strategy.key))["enabled"])

    def set_slack_history_sync_enabled(
        self, _db: Any, *, tenant_id: UUID, enabled: bool
    ) -> object:
        strategy = get_schedule_kind(SLACK_HISTORY_SYNC_KEY)
        current = self._raw(tenant_id, strategy.key) or {}
        block = strategy.apply_patch(current, {"enabled": enabled})
        self._put(tenant_id, strategy.key, block)
        return object()

    def get_recurring_report_schedule(self, _db: Any, tenant_id: UUID) -> dict[str, Any]:
        strategy = get_schedule_kind(RECURRING_REPORT_KEY)
        return strategy.normalize(self._raw(tenant_id, strategy.key))

    def set_recurring_report_schedule(
        self,
        _db: Any,
        *,
        tenant_id: UUID,
        enabled: bool | None = None,
        channel_id: str | None = None,
        cadence: str | None = None,
        window_label: str | None = None,
        clear_channel: bool = False,
    ) -> object:
        strategy = get_schedule_kind(RECURRING_REPORT_KEY)
        patch: dict[str, Any] = {"clear_channel": clear_channel}
        if enabled is not None:
            patch["enabled"] = enabled
        if channel_id is not None:
            patch["channel_id"] = channel_id
        if cadence is not None:
            patch["cadence"] = cadence
        if window_label is not None:
            patch["window_label"] = window_label
        current = self._raw(tenant_id, strategy.key) or {}
        block = strategy.apply_patch(current, patch)
        self._put(tenant_id, strategy.key, block)
        return object()

    def read_all_kinds(self, _db: Any, tenant_id: UUID) -> dict[str, Any]:
        return {
            SLACK_HISTORY_SYNC_KEY: get_schedule_kind(SLACK_HISTORY_SYNC_KEY).normalize(
                self._raw(tenant_id, SLACK_HISTORY_SYNC_KEY)
            ),
            RECURRING_REPORT_KEY: get_schedule_kind(RECURRING_REPORT_KEY).normalize(
                self._raw(tenant_id, RECURRING_REPORT_KEY)
            ),
        }

    def patch_schedules(
        self,
        _db: Any,
        *,
        tenant_id: UUID,
        slack_history_sync: dict[str, Any] | None = None,
        recurring_report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if slack_history_sync is None and recurring_report is None:
            raise ValueError("at least one schedule kind patch required")
        if slack_history_sync is not None:
            strategy = get_schedule_kind(SLACK_HISTORY_SYNC_KEY)
            current = self._raw(tenant_id, strategy.key) or {}
            self._put(
                tenant_id,
                strategy.key,
                strategy.apply_patch(current, slack_history_sync),
            )
        if recurring_report is not None:
            strategy = get_schedule_kind(RECURRING_REPORT_KEY)
            current = self._raw(tenant_id, strategy.key) or {}
            self._put(
                tenant_id,
                strategy.key,
                strategy.apply_patch(current, recurring_report),
            )
        return self.read_all_kinds(_db, tenant_id)


__all__ = [
    "FakeScheduleDB",
    "MemorySchedules",
    "report_block",
    "sync_block",
]

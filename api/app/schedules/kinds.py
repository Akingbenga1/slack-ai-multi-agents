"""ScheduleKindStrategy map — per-key validate / defaults / due (Sprint 28.2).

Smell: twin schedule modules each owned defaults + Beat predicates. Strategy
per key; new kind = class + registry entry. Persistence stays on ScheduleStore.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.billing.plans import tenant_has_entitlement

Cadence = Literal["daily", "weekly"]

SLACK_HISTORY_SYNC_KEY = "slack_history_sync"
RECURRING_REPORT_KEY = "recurring_report"

_CADENCE_WINDOWS: dict[str, str] = {
    "daily": "last 24 hours",
    "weekly": "last 7 days",
}


def normalize_cadence(value: str | None) -> Cadence:
    raw = (value or "weekly").strip().lower()
    if raw not in ("daily", "weekly"):
        raise ValueError("cadence must be 'daily' or 'weekly'")
    return raw  # type: ignore[return-value]


def window_label_for_cadence(cadence: str | None) -> str:
    key = normalize_cadence(cadence)
    return _CADENCE_WINDOWS[key]


class ScheduleKindStrategy(Protocol):
    """Strategy contract for one ``AgentConfig.schedules`` key."""

    key: str

    def defaults(self) -> dict[str, Any]:
        """Canonical default block (create / normalize baseline)."""
        ...

    def normalize(self, block: dict[str, Any] | None) -> dict[str, Any]:
        """Validate + fill defaults for reads / API responses."""
        ...

    def apply_patch(self, current: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        """
        Merge a partial update onto ``current`` (already normalized or {}).

        Raises ``ValueError`` on invalid fields.
        """
        ...

    def is_due(
        self,
        db: Session,
        tenant_id: UUID,
        block: dict[str, Any],
        **filters: Any,
    ) -> bool:
        """Beat listing predicate (entitlement + kind-specific gates)."""
        ...


class SlackHistorySyncStrategy:
    key = SLACK_HISTORY_SYNC_KEY
    # Missing / unset → enabled for Beat (default hourly).
    default_enabled = True

    def defaults(self) -> dict[str, Any]:
        return {"enabled": self.default_enabled}

    def normalize(self, block: dict[str, Any] | None) -> dict[str, Any]:
        raw = block if isinstance(block, dict) else {}
        if "enabled" not in raw:
            return {"enabled": self.default_enabled}
        return {"enabled": bool(raw["enabled"])}

    def apply_patch(
        self, current: dict[str, Any], patch: dict[str, Any]
    ) -> dict[str, Any]:
        out = dict(self.normalize(current))
        if "enabled" in patch and patch["enabled"] is not None:
            out["enabled"] = bool(patch["enabled"])
        return out

    def is_due(
        self,
        db: Session,
        tenant_id: UUID,
        block: dict[str, Any],
        **filters: Any,
    ) -> bool:
        _ = filters
        if not tenant_has_entitlement(db, tenant_id, "sync"):
            return False
        return bool(self.normalize(block)["enabled"])


class RecurringReportStrategy:
    key = RECURRING_REPORT_KEY
    default_enabled = False
    default_cadence: Cadence = "weekly"

    def defaults(self) -> dict[str, Any]:
        return {
            "enabled": self.default_enabled,
            "cadence": self.default_cadence,
            "channel_id": None,
            "window_label": window_label_for_cadence(self.default_cadence),
        }

    def normalize(self, block: dict[str, Any] | None) -> dict[str, Any]:
        raw = block if isinstance(block, dict) else {}
        enabled = (
            bool(raw["enabled"]) if "enabled" in raw else self.default_enabled
        )
        cadence = normalize_cadence(
            str(raw.get("cadence") or self.default_cadence)
            if raw.get("cadence") is not None
            else self.default_cadence
        )
        channel_id = raw.get("channel_id")
        channel = str(channel_id).strip() if channel_id else None
        if channel == "":
            channel = None
        window = str(raw.get("window_label") or "").strip() or window_label_for_cadence(
            cadence
        )
        return {
            "enabled": enabled,
            "channel_id": channel,
            "cadence": cadence,
            "window_label": window,
        }

    def apply_patch(
        self, current: dict[str, Any], patch: dict[str, Any]
    ) -> dict[str, Any]:
        out = dict(self.normalize(current))
        if patch.get("enabled") is not None:
            out["enabled"] = bool(patch["enabled"])
        if patch.get("clear_channel"):
            out["channel_id"] = None
        elif patch.get("channel_id") is not None:
            cleaned = str(patch["channel_id"]).strip()
            out["channel_id"] = cleaned or None
        if patch.get("cadence") is not None:
            out["cadence"] = normalize_cadence(str(patch["cadence"]))
            if patch.get("window_label") is None:
                out["window_label"] = window_label_for_cadence(out["cadence"])
        if patch.get("window_label") is not None:
            label = str(patch["window_label"]).strip()
            out["window_label"] = label or window_label_for_cadence(
                str(out.get("cadence") or self.default_cadence)
            )
        return out

    def is_due(
        self,
        db: Session,
        tenant_id: UUID,
        block: dict[str, Any],
        **filters: Any,
    ) -> bool:
        if not tenant_has_entitlement(db, tenant_id, "agent"):
            return False
        sched = self.normalize(block)
        if not sched["enabled"]:
            return False
        if not sched["channel_id"]:
            return False
        cadence_filter = filters.get("cadence")
        if cadence_filter is not None and sched["cadence"] != cadence_filter:
            return False
        return True


_SYNC = SlackHistorySyncStrategy()
_REPORT = RecurringReportStrategy()

SCHEDULE_KIND_STRATEGIES: dict[str, ScheduleKindStrategy] = {
    SLACK_HISTORY_SYNC_KEY: _SYNC,
    RECURRING_REPORT_KEY: _REPORT,
}


def get_schedule_kind(key: str) -> ScheduleKindStrategy:
    strategy = SCHEDULE_KIND_STRATEGIES.get(key)
    if strategy is None:
        raise KeyError(f"unknown schedule kind: {key}")
    return strategy


def list_due_for_kind(
    db: Session,
    key: str,
    **filters: Any,
) -> list[UUID]:
    """Tenant ids due for Beat for ``key`` (store + Strategy.is_due)."""
    from api.app.schedules.store import list_tenants_for

    strategy = get_schedule_kind(key)

    def predicate(tenant_id: UUID, block: dict[str, Any]) -> bool:
        return strategy.is_due(db, tenant_id, block, **filters)

    return list_tenants_for(db, key, predicate)


def list_due_recurring_reports(
    db: Session,
    *,
    cadence: Cadence | None = None,
) -> list[dict[str, Any]]:
    """Enriched due rows for recurring-report Beat ticks."""
    strategy = _REPORT
    filters: dict[str, Any] = {}
    if cadence is not None:
        filters["cadence"] = cadence
    due_ids = list_due_for_kind(db, strategy.key, **filters)
    rows: list[dict[str, Any]] = []
    from api.app.schedules.store import get_block

    for tenant_id in due_ids:
        sched = strategy.normalize(get_block(db, tenant_id, strategy.key))
        rows.append(
            {
                "tenant_id": tenant_id,
                "channel_id": sched["channel_id"],
                "cadence": sched["cadence"],
                "window_label": sched["window_label"],
            }
        )
    return rows


__all__ = [
    "Cadence",
    "RECURRING_REPORT_KEY",
    "SCHEDULE_KIND_STRATEGIES",
    "SLACK_HISTORY_SYNC_KEY",
    "RecurringReportStrategy",
    "ScheduleKindStrategy",
    "SlackHistorySyncStrategy",
    "get_schedule_kind",
    "list_due_for_kind",
    "list_due_recurring_reports",
    "normalize_cadence",
    "window_label_for_cadence",
]

"""ScheduleKindStrategy map — per-key validate / defaults / due (Sprint 28.2).

Smell: twin schedule modules each owned defaults + Beat predicates. Strategy
per key; new kind = class + registry entry. Persistence stays on ScheduleStore.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.billing.plans import tenants_with_entitlement

Cadence = Literal["daily", "weekly"]

SLACK_HISTORY_SYNC_KEY = "slack_history_sync"
RECURRING_REPORT_KEY = "recurring_report"

_CADENCE_WINDOWS: dict[str, str] = {
    "daily": "last 24 hours",
    "weekly": "last 7 days",
}

_ENTITLEMENT_BY_KEY: dict[str, str] = {
    SLACK_HISTORY_SYNC_KEY: "sync",
    RECURRING_REPORT_KEY: "agent",
}


def normalize_cadence(value: str | None) -> Cadence:
    raw = (value or "weekly").strip().lower()
    if raw not in ("daily", "weekly"):
        raise ValueError("cadence must be 'daily' or 'weekly'")
    return raw  # type: ignore[return-value]


def window_label_for_cadence(cadence: str | None) -> str:
    key = normalize_cadence(cadence)
    return _CADENCE_WINDOWS[key]


def period_key_for_cadence(
    cadence: str | None,
    when: datetime | None = None,
) -> str:
    """
    Idempotency period for a Beat cadence (UTC).

    daily → ``YYYY-MM-DD``; weekly → ``YYYY-Www`` (ISO week).
    """
    key = normalize_cadence(cadence)
    moment = when or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    else:
        moment = moment.astimezone(timezone.utc)
    if key == "daily":
        return moment.strftime("%Y-%m-%d")
    iso = moment.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


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

    def block_is_due(self, block: dict[str, Any], **filters: Any) -> bool:
        """Kind-specific due gate (no DB / entitlement)."""
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

    def block_is_due(self, block: dict[str, Any], **filters: Any) -> bool:
        _ = filters
        return bool(self.normalize(block)["enabled"])

    def is_due(
        self,
        db: Session,
        tenant_id: UUID,
        block: dict[str, Any],
        **filters: Any,
    ) -> bool:
        entitled = filters.get("_entitled")
        if entitled is None:
            entitled = tenant_id in tenants_with_entitlement(db, [tenant_id], "sync")
        if not entitled:
            return False
        return self.block_is_due(block, **filters)


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
        out: dict[str, Any] = {
            "enabled": enabled,
            "channel_id": channel,
            "cadence": cadence,
            "window_label": window,
        }
        # Internal Beat idempotency bookkeeping (preserved across patches).
        last_period = raw.get("last_posted_period")
        if last_period:
            out["last_posted_period"] = str(last_period)
        last_at = raw.get("last_posted_at")
        if last_at:
            out["last_posted_at"] = str(last_at)
        return out

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
        if patch.get("last_posted_period") is not None:
            out["last_posted_period"] = str(patch["last_posted_period"])
        if patch.get("last_posted_at") is not None:
            out["last_posted_at"] = str(patch["last_posted_at"])
        return out

    def block_is_due(self, block: dict[str, Any], **filters: Any) -> bool:
        sched = self.normalize(block)
        if not sched["enabled"]:
            return False
        if not sched["channel_id"]:
            return False
        cadence_filter = filters.get("cadence")
        if cadence_filter is not None and sched["cadence"] != cadence_filter:
            return False
        now = filters.get("now")
        period = period_key_for_cadence(sched["cadence"], when=now)
        if sched.get("last_posted_period") == period:
            return False
        return True

    def is_due(
        self,
        db: Session,
        tenant_id: UUID,
        block: dict[str, Any],
        **filters: Any,
    ) -> bool:
        entitled = filters.get("_entitled")
        if entitled is None:
            entitled = tenant_id in tenants_with_entitlement(db, [tenant_id], "agent")
        if not entitled:
            return False
        return self.block_is_due(block, **filters)


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
    """Tenant ids due for Beat for ``key`` (bulk configs + entitlements)."""
    from api.app.schedules.store import list_candidate_tenant_ids, load_blocks_for

    strategy = get_schedule_kind(key)
    flag = _ENTITLEMENT_BY_KEY.get(key)
    ids = list_candidate_tenant_ids(db)
    entitled: set[UUID]
    if flag:
        entitled = tenants_with_entitlement(db, ids, flag)
    else:
        entitled = set(ids)
    blocks = load_blocks_for(db, key, ids)

    due: list[UUID] = []
    for tenant_id in ids:
        if tenant_id not in entitled:
            continue
        if strategy.block_is_due(blocks.get(tenant_id, {}), **filters):
            due.append(tenant_id)
    return due


def list_due_recurring_reports(
    db: Session,
    *,
    cadence: Cadence | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Enriched due rows for recurring-report Beat ticks."""
    strategy = _REPORT
    filters: dict[str, Any] = {}
    if cadence is not None:
        filters["cadence"] = cadence
    if now is not None:
        filters["now"] = now
    from api.app.schedules.store import list_candidate_tenant_ids, load_blocks_for

    ids = list_candidate_tenant_ids(db)
    entitled = tenants_with_entitlement(db, ids, "agent")
    blocks = load_blocks_for(db, strategy.key, ids)
    rows: list[dict[str, Any]] = []
    for tenant_id in ids:
        if tenant_id not in entitled:
            continue
        raw = blocks.get(tenant_id, {})
        if not strategy.block_is_due(raw, **filters):
            continue
        sched = strategy.normalize(raw)
        rows.append(
            {
                "tenant_id": tenant_id,
                "channel_id": sched["channel_id"],
                "cadence": sched["cadence"],
                "window_label": sched["window_label"],
                "period": period_key_for_cadence(sched["cadence"], when=now),
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
    "period_key_for_cadence",
    "window_label_for_cadence",
]

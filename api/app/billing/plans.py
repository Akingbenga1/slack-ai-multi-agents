"""Plan activation / deactivation + entitlements (Sprint 11.4–11.5)."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.db.models import BillingCustomer, Tenant
from api.app.logging_config import get_logger

logger = get_logger("api.billing.plans")

_UNSET = object()

# Stripe subscription statuses that grant product access
_ACTIVE_STATUSES = frozenset({"active", "trialing"})

# Product flags + default budgets when plan is active (Sprint 12)
# Budget keys are ints; feature flags are bools.
ACTIVE_ENTITLEMENTS: dict[str, bool | int] = {
    "agent": True,
    "ingest": True,
    "sync": True,
    "tokens_daily": 100_000,
    "tokens_monthly": 2_000_000,
    "jobs_daily": 50,
}

INACTIVE_ENTITLEMENTS: dict[str, bool | int] = {
    "agent": False,
    "ingest": False,
    "sync": False,
    "tokens_daily": 0,
    "tokens_monthly": 0,
    "jobs_daily": 0,
}

BUDGET_KEYS = frozenset({"tokens_daily", "tokens_monthly", "jobs_daily"})

PLAN_SOURCES = frozenset({"admin", "stripe"})
ALLOWED_PLAN_STATUSES = frozenset({"active", "inactive"})


def plan_is_admin_locked(row: BillingCustomer) -> bool:
    """True when an operator waiver blocks Stripe webhook plan updates."""
    return (row.plan_source or "stripe").strip().lower() == "admin"


def plan_status_from_stripe(subscription_status: str | None) -> str:
    """Map Stripe subscription.status → local plan_status."""
    if (subscription_status or "").strip().lower() in _ACTIVE_STATUSES:
        return "active"
    return "inactive"


def entitlements_for_plan_status(plan_status: str) -> dict[str, bool | int]:
    if (plan_status or "").strip().lower() == "active":
        return dict(ACTIVE_ENTITLEMENTS)
    return dict(INACTIVE_ENTITLEMENTS)


def get_tenant_entitlements(db: Session, tenant_id: UUID | str) -> dict[str, bool | int]:
    """Return entitlements/budgets for tenant; empty if no billing row."""
    row = db.scalar(
        select(BillingCustomer).where(BillingCustomer.tenant_id == UUID(str(tenant_id)))
    )
    if row is None:
        return {}
    return dict(row.entitlements or {})


def tenant_has_entitlement(
    db: Session,
    tenant_id: UUID | str,
    flag: str,
) -> bool:
    """Return True if the tenant's billing row grants `flag` (e.g. agent)."""
    return UUID(str(tenant_id)) in tenants_with_entitlement(db, [tenant_id], flag)


def tenants_with_entitlement(
    db: Session,
    tenant_ids: list[UUID | str] | tuple[UUID | str, ...] | set[UUID | str],
    flag: str,
) -> set[UUID]:
    """
    Bulk entitlement check — one billing query + one suspended-tenant query.

    Used by Beat due-lists to avoid N+1 ``tenant_has_entitlement`` calls.
    """
    ids = [UUID(str(t)) for t in tenant_ids]
    if not ids:
        return set()
    suspended = {
        row.id
        for row in db.scalars(
            select(Tenant).where(
                Tenant.id.in_(ids),
                Tenant.status == "suspended",
            )
        ).all()
    }
    active: set[UUID] = set()
    for row in db.scalars(
        select(BillingCustomer).where(BillingCustomer.tenant_id.in_(ids))
    ).all():
        if row.tenant_id in suspended:
            continue
        if (row.plan_status or "").lower() != "active":
            continue
        ents = row.entitlements or {}
        if bool(ents.get(flag)):
            active.add(row.tenant_id)
    return active


def require_entitlement(db: Session, tenant_id: UUID | str, flag: str) -> None:
    """Raise HTTP 403 when the tenant lacks an active plan entitlement flag."""
    from fastapi import HTTPException, status

    if not tenant_has_entitlement(db, tenant_id, flag):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "entitlement_denied", "flag": flag},
        )


def tenant_is_suspended(db: Session, tenant_id: UUID | str) -> bool:
    row = db.get(Tenant, UUID(str(tenant_id)))
    return bool(row and (row.status or "").lower() == "suspended")


def plan_is_active(db: Session, tenant_id: UUID | str) -> bool:
    tid = UUID(str(tenant_id))
    if tenant_is_suspended(db, tid):
        return False
    row = db.scalar(
        select(BillingCustomer).where(BillingCustomer.tenant_id == tid)
    )
    return bool(row and (row.plan_status or "").lower() == "active")


def get_billing_by_external_customer(
    db: Session, external_customer_id: str
) -> BillingCustomer | None:
    if not external_customer_id:
        return None
    return db.scalar(
        select(BillingCustomer).where(
            BillingCustomer.external_customer_id == external_customer_id
        )
    )


# Backward-compatible alias (Sprint 34)
get_billing_by_stripe_customer = get_billing_by_external_customer


def get_billing_by_subscription(
    db: Session, external_subscription_id: str
) -> BillingCustomer | None:
    if not external_subscription_id:
        return None
    return db.scalar(
        select(BillingCustomer).where(
            BillingCustomer.external_subscription_id == external_subscription_id
        )
    )


def apply_plan_state(
    db: Session,
    row: BillingCustomer,
    *,
    plan_status: str,
    external_subscription_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    clear_subscription: bool = False,
    extra_meta: Optional[dict[str, Any]] = None,
    plan_source: Optional[str] = None,
    override_reason: Optional[str] | object = _UNSET,
) -> BillingCustomer:
    """Persist plan_status, subscription id, entitlement flags, and plan source."""
    # stripe_subscription_id kept as deprecated alias for Sprint 34 callers
    sub_id = external_subscription_id if external_subscription_id is not None else stripe_subscription_id
    row.plan_status = plan_status
    row.entitlements = entitlements_for_plan_status(plan_status)
    if clear_subscription:
        row.external_subscription_id = None
    elif sub_id:
        row.external_subscription_id = sub_id
    if plan_source is not None:
        source_n = (plan_source or "stripe").strip().lower()
        if source_n not in PLAN_SOURCES:
            raise ValueError(f"plan_source must be one of {sorted(PLAN_SOURCES)}")
        row.plan_source = source_n
    if override_reason is not _UNSET:
        row.override_reason = override_reason  # type: ignore[assignment]
    if extra_meta:
        meta = dict(row.meta or {})
        meta.update(extra_meta)
        row.meta = meta
    db.add(row)
    db.flush()
    logger.info(
        "plan_state_applied tenant_id=%s plan_status=%s plan_source=%s subscription_id=%s entitlements=%s",
        row.tenant_id,
        row.plan_status,
        row.plan_source,
        row.external_subscription_id,
        row.entitlements,
    )
    return row


def resolve_tenant_id_from_checkout(session_obj: Any) -> UUID | None:
    """Prefer client_reference_id, then metadata.tenant_id / client_id."""
    ref = _attr(session_obj, "client_reference_id")
    if ref:
        try:
            return UUID(str(ref))
        except ValueError:
            pass
    meta = _attr(session_obj, "metadata") or {}
    if isinstance(meta, dict):
        for key in ("tenant_id", "client_id"):
            raw = meta.get(key)
            if raw:
                try:
                    return UUID(str(raw))
                except ValueError:
                    continue
    return None


def resolve_tenant_id_from_subscription(sub_obj: Any) -> UUID | None:
    meta = _attr(sub_obj, "metadata") or {}
    if isinstance(meta, dict):
        for key in ("tenant_id", "client_id"):
            raw = meta.get(key)
            if raw:
                try:
                    return UUID(str(raw))
                except ValueError:
                    continue
    return None


def _attr(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)

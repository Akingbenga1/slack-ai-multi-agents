"""Support actions + audit log (Sprint 21.3)."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.billing.customers import ensure_billing_customer
from api.app.billing.plans import BUDGET_KEYS
from api.app.db.models import AuditLog, BillingCustomer, Tenant
from api.app.logging_config import get_logger

logger = get_logger("api.admin.actions")

ALLOWED_TENANT_STATUSES = frozenset({"active", "suspended"})


def write_audit_log(
    db: Session,
    *,
    actor_user_id: UUID | str | None,
    actor_email: str | None,
    action: str,
    tenant_id: UUID | str | None = None,
    detail: Optional[dict[str, Any]] = None,
    commit: bool = False,
) -> AuditLog:
    row = AuditLog(
        actor_user_id=UUID(str(actor_user_id)) if actor_user_id else None,
        actor_email=(actor_email or None),
        action=action,
        tenant_id=UUID(str(tenant_id)) if tenant_id else None,
        detail=detail or {},
    )
    db.add(row)
    db.flush()
    if commit:
        db.commit()
        db.refresh(row)
    logger.info(
        "audit_log action=%s tenant_id=%s actor=%s",
        action,
        tenant_id,
        actor_email,
    )
    return row


def set_tenant_status(
    db: Session,
    tenant_id: UUID | str,
    *,
    status: str,
    actor_user_id: UUID | str | None,
    actor_email: str | None,
) -> Tenant:
    status_n = (status or "").strip().lower()
    if status_n not in ALLOWED_TENANT_STATUSES:
        raise ValueError(f"status must be one of {sorted(ALLOWED_TENANT_STATUSES)}")

    tid = UUID(str(tenant_id))
    tenant = db.get(Tenant, tid)
    if tenant is None:
        raise LookupError("tenant not found")

    before = tenant.status
    tenant.status = status_n
    db.add(tenant)
    write_audit_log(
        db,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action="tenant.status.set",
        tenant_id=tid,
        detail={"before": before, "after": status_n},
    )
    db.commit()
    db.refresh(tenant)
    return tenant


def override_tenant_budgets(
    db: Session,
    tenant_id: UUID | str,
    *,
    budgets: dict[str, int],
    actor_user_id: UUID | str | None,
    actor_email: str | None,
) -> BillingCustomer:
    """Merge numeric budget keys into billing entitlements (support override)."""
    tid = UUID(str(tenant_id))
    tenant = db.get(Tenant, tid)
    if tenant is None:
        raise LookupError("tenant not found")

    cleaned: dict[str, int] = {}
    for key, raw in (budgets or {}).items():
        if key not in BUDGET_KEYS:
            raise ValueError(f"unknown budget key: {key}")
        try:
            val = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"budget {key} must be an int") from exc
        if val < 0:
            raise ValueError(f"budget {key} must be >= 0")
        cleaned[key] = val

    if not cleaned:
        raise ValueError("no budget keys provided")

    row = ensure_billing_customer(db, tenant_id=tid, create_stripe=False)
    before = {k: (row.entitlements or {}).get(k) for k in cleaned}
    ents = dict(row.entitlements or {})
    ents.update(cleaned)
    row.entitlements = ents
    meta = dict(row.meta or {})
    meta["budget_override"] = {
        "keys": cleaned,
        "by": actor_email,
    }
    row.meta = meta
    db.add(row)
    write_audit_log(
        db,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action="tenant.budget.override",
        tenant_id=tid,
        detail={"before": before, "after": cleaned},
    )
    db.commit()
    db.refresh(row)
    return row


def list_audit_logs(
    db: Session,
    *,
    tenant_id: UUID | str | None = None,
    limit: int = 50,
) -> list[AuditLog]:
    lim = max(1, min(int(limit), 200))
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(lim)
    if tenant_id is not None:
        stmt = stmt.where(AuditLog.tenant_id == UUID(str(tenant_id)))
    return list(db.scalars(stmt).all())

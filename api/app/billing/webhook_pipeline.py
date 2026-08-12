"""Webhook Template Method: verify → map → ``apply_plan_state`` (Sprint 34.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.billing.customers import get_billing_customer
from api.app.billing.plans import (
    apply_plan_state,
    get_billing_by_external_customer,
    get_billing_by_subscription,
    plan_is_admin_locked,
)
from api.app.logging_config import get_logger

logger = get_logger("api.billing.webhook_pipeline")


@dataclass
class MappedPlanEvent:
    """Provider-neutral plan update produced by an adapter event map."""

    event_type: str
    plan_status: Optional[str] = None
    tenant_id: Optional[UUID] = None
    external_customer_id: Optional[str] = None
    external_subscription_id: Optional[str] = None
    clear_subscription: bool = False
    handled: bool = True
    skip_reason: Optional[str] = None
    extra_meta: dict[str, Any] = field(default_factory=dict)


def process_payment_webhook(
    db: Session,
    provider: Any,
    payload: bytes,
    signature_header: str,
) -> dict[str, Any]:
    """
    Template Method skeleton for payment webhooks.

    1. ``provider.verify_webhook`` — signature / payload check
    2. ``provider.map_webhook_event`` — adapter-owned vendor → ``MappedPlanEvent``
    3. ``apply_mapped_plan_event`` — resolve row, honour admin lock, ``apply_plan_state``
    """
    event = provider.verify_webhook(payload, signature_header)
    return handle_mapped_webhook(db, provider, event)


def handle_mapped_webhook(db: Session, provider: Any, event: Any) -> dict[str, Any]:
    """Steps 2–3 of the Template Method (event already verified)."""
    mapped = provider.map_webhook_event(event)
    if mapped is None:
        event_type = _attr(event, "type") or ""
        logger.info("payment_webhook_ignored provider=%s type=%s", provider.name, event_type)
        return {"handled": False, "type": event_type}
    return apply_mapped_plan_event(db, provider, mapped)


def apply_mapped_plan_event(
    db: Session,
    provider: Any,
    mapped: MappedPlanEvent,
) -> dict[str, Any]:
    """Shared apply step — product entitlements, not vendor-specific."""
    if not mapped.handled:
        return {
            "handled": False,
            "type": mapped.event_type,
            "reason": mapped.skip_reason or "skipped",
        }

    row = _resolve_billing_row(db, mapped)
    if row is None:
        logger.warning(
            "payment_webhook_no_billing_row type=%s tenant_id=%s customer=%s",
            mapped.event_type,
            mapped.tenant_id,
            mapped.external_customer_id,
        )
        return {"handled": False, "reason": "billing_row_not_found", "type": mapped.event_type}

    if plan_is_admin_locked(row):
        logger.info(
            "payment_webhook_skipped_admin_lock tenant_id=%s type=%s",
            row.tenant_id,
            mapped.event_type,
        )
        return {"handled": False, "reason": "admin_plan_lock", "type": mapped.event_type}

    if mapped.external_customer_id and not row.external_customer_id:
        row.external_customer_id = mapped.external_customer_id
        row.provider = row.provider or provider.name

    if mapped.plan_status is None:
        return {"handled": False, "reason": "no_plan_status", "type": mapped.event_type}

    apply_plan_state(
        db,
        row,
        plan_status=mapped.plan_status,
        external_subscription_id=mapped.external_subscription_id,
        clear_subscription=mapped.clear_subscription,
        plan_source=provider.name,
        override_reason=None,
        extra_meta=mapped.extra_meta or None,
    )
    return {
        "handled": True,
        "type": mapped.event_type,
        "tenant_id": str(row.tenant_id),
        "plan_status": row.plan_status,
    }


def _resolve_billing_row(db: Session, mapped: MappedPlanEvent):
    if mapped.tenant_id is not None:
        row = get_billing_customer(db, mapped.tenant_id)
        if row is not None:
            return row
    if mapped.external_subscription_id:
        row = get_billing_by_subscription(db, mapped.external_subscription_id)
        if row is not None:
            return row
    if mapped.external_customer_id:
        return get_billing_by_external_customer(db, mapped.external_customer_id)
    return None


def _attr(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)

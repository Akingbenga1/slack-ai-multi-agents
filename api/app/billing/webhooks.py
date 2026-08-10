"""Stripe webhook verification + plan lifecycle handlers (Task 11.4)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from api.app.billing.customers import get_billing_customer
from api.app.billing.plans import (
    apply_plan_state,
    get_billing_by_stripe_customer,
    get_billing_by_subscription,
    plan_status_from_stripe,
    resolve_tenant_id_from_checkout,
    resolve_tenant_id_from_subscription,
)
from api.app.billing.stripe_client import configure_stripe
from api.app.logging_config import get_logger
from api.app.settings import Settings

logger = get_logger("api.billing.webhooks")


class WebhookError(RuntimeError):
    """Webhook processing / verification failure."""


def construct_stripe_event(payload: bytes, sig_header: str, settings: Settings) -> Any:
    """Verify signature and return a Stripe Event."""
    secret = (settings.stripe_webhook_secret or "").strip()
    if not secret:
        raise WebhookError("STRIPE_WEBHOOK_SECRET is not set")
    if not sig_header:
        raise WebhookError("Missing Stripe-Signature header")

    configure_stripe(settings)
    import stripe

    try:
        return stripe.Webhook.construct_event(payload, sig_header, secret)
    except ValueError as exc:
        raise WebhookError(f"Invalid webhook payload: {exc}") from exc
    except stripe.error.SignatureVerificationError as exc:
        raise WebhookError(f"Invalid Stripe signature: {exc}") from exc


def handle_stripe_event(db: Session, event: Any) -> dict[str, Any]:
    """
    Apply plan changes for supported event types.

    Returns a small summary dict for logging / response. Unknown types are ignored.
    """
    event_type = _attr(event, "type") or ""
    data_object = _nested(event, "data", "object")

    if event_type == "checkout.session.completed":
        return _handle_checkout_completed(db, data_object)
    if event_type == "customer.subscription.updated":
        return _handle_subscription_updated(db, data_object)
    if event_type == "customer.subscription.deleted":
        return _handle_subscription_deleted(db, data_object)

    logger.info("stripe_webhook_ignored type=%s", event_type)
    return {"handled": False, "type": event_type}


def _handle_checkout_completed(db: Session, session_obj: Any) -> dict[str, Any]:
    mode = _attr(session_obj, "mode")
    if mode and mode != "subscription":
        return {"handled": False, "reason": "not_subscription_mode"}

    tenant_id = resolve_tenant_id_from_checkout(session_obj)
    customer_id = _attr(session_obj, "customer")
    subscription_id = _attr(session_obj, "subscription")

    row = None
    if tenant_id is not None:
        row = get_billing_customer(db, tenant_id)
    if row is None and customer_id:
        row = get_billing_by_stripe_customer(db, str(customer_id))

    if row is None:
        logger.warning(
            "checkout_completed_no_billing_row tenant_id=%s customer=%s",
            tenant_id,
            customer_id,
        )
        return {"handled": False, "reason": "billing_row_not_found"}

    if customer_id and not row.stripe_customer_id:
        row.stripe_customer_id = str(customer_id)

    apply_plan_state(
        db,
        row,
        plan_status="active",
        stripe_subscription_id=str(subscription_id) if subscription_id else None,
        extra_meta={"last_checkout_session_id": _attr(session_obj, "id")},
    )
    return {
        "handled": True,
        "type": "checkout.session.completed",
        "tenant_id": str(row.tenant_id),
        "plan_status": row.plan_status,
    }


def _handle_subscription_updated(db: Session, sub_obj: Any) -> dict[str, Any]:
    row = _resolve_row_for_subscription(db, sub_obj)
    if row is None:
        return {"handled": False, "reason": "billing_row_not_found"}

    status = _attr(sub_obj, "status")
    plan_status = plan_status_from_stripe(str(status) if status else None)
    sub_id = _attr(sub_obj, "id")
    apply_plan_state(
        db,
        row,
        plan_status=plan_status,
        stripe_subscription_id=str(sub_id) if sub_id else None,
        extra_meta={"stripe_subscription_status": status},
    )
    return {
        "handled": True,
        "type": "customer.subscription.updated",
        "tenant_id": str(row.tenant_id),
        "plan_status": row.plan_status,
    }


def _handle_subscription_deleted(db: Session, sub_obj: Any) -> dict[str, Any]:
    row = _resolve_row_for_subscription(db, sub_obj)
    if row is None:
        return {"handled": False, "reason": "billing_row_not_found"}

    apply_plan_state(
        db,
        row,
        plan_status="inactive",
        clear_subscription=True,
        extra_meta={"stripe_subscription_status": "canceled"},
    )
    return {
        "handled": True,
        "type": "customer.subscription.deleted",
        "tenant_id": str(row.tenant_id),
        "plan_status": row.plan_status,
    }


def _resolve_row_for_subscription(db: Session, sub_obj: Any):
    tenant_id = resolve_tenant_id_from_subscription(sub_obj)
    if tenant_id is not None:
        row = get_billing_customer(db, tenant_id)
        if row is not None:
            return row
    sub_id = _attr(sub_obj, "id")
    if sub_id:
        row = get_billing_by_subscription(db, str(sub_id))
        if row is not None:
            return row
    customer_id = _attr(sub_obj, "customer")
    if customer_id:
        return get_billing_by_stripe_customer(db, str(customer_id))
    return None


def _attr(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _nested(obj: Any, *path: str) -> Any:
    cur = obj
    for key in path:
        cur = _attr(cur, key)
        if cur is None:
            return None
    return cur
